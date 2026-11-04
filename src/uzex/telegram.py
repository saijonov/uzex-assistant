import asyncio
import contextlib
import fcntl
import json
import logging
import signal
import time

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramConflictError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from uzex.config import Settings, require_credentials
from uzex.downloads import requested_source_file, source_csv
from uzex.engine import Engine, guess_language
from uzex.interface import greeting, main_keyboard, menu_action, telegram_html
from uzex.interface import text as ui_text
from uzex.models import Answer
from uzex.policy import attach_csv, export_followup, file_preference, resolve_pending_reply
from uzex.render import (
    all_shown_text,
    error_text,
    export_csv,
    memory_text,
    render_answer,
    render_sources,
    split_text,
    tr,
)
from uzex.state import State

logger = logging.getLogger(__name__)


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="O‘zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
            ]
        ]
    )


def pagination_keyboard(job_id: str, language: str, row_count: int, page: int = 0):
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text=tr(("Oldingi 10 ta", "Предыдущие 10"), language),
                callback_data=f"page:{job_id}:{page - 1}",
            )
        )
    if (page + 1) * 10 < row_count:
        navigation.append(
            InlineKeyboardButton(
                text=tr(("Keyingi 10 ta", "Следующие 10"), language),
                callback_data=f"page:{job_id}:{page + 1}",
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[navigation]) if navigation else None


def csv_caption(answer: Answer) -> str:
    data = answer.evidence
    rows, columns = len(data.rows), len(data.rows[0]) if data.rows else 0
    caption = tr(
        (
            f"Javob jadvali\nQatorlar: {rows}. Ustunlar: {columns}.",
            f"Таблица ответа\nСтрок: {rows}. Столбцов: {columns}.",
        ),
        answer.language,
    )
    if data.capped:
        total = f"{data.matched_count:,}".replace(",", " ")
        caption += tr(
            (f"\nDastlabki {data.row_limit} qator.", f"\nПервые {data.row_limit} строк."),
            answer.language,
        )
        if not data.grouped:
            caption += tr(
                (f" Jami mos yozuvlar: {total}.", f" Всего подходящих записей: {total}."),
                answer.language,
            )
    return caption


class Service:
    def __init__(self, bot: Bot, state: State, engine: Engine):
        self.bot, self.state, self.engine = bot, state, engine
        self.stopping = asyncio.Event()

    async def typing(self, chat_id: int):
        while True:
            with contextlib.suppress(TelegramAPIError):
                await self.bot.send_chat_action(chat_id, "typing", request_timeout=3)
            await asyncio.sleep(4)

    async def publish_commands(self, language: str, chat_id: int | None = None):
        commands = [
            ("start", ("Boshlash", "Начало")),
            ("menu", ("Menyu", "Меню")),
            ("examples", ("Savol namunalari", "Примеры вопросов")),
            ("help", ("Yordam", "Помощь")),
            ("language", ("Tilni o‘zgartirish", "Сменить язык")),
            ("reset", ("Yangi suhbat", "Новый диалог")),
        ]
        options = (
            {"scope": BotCommandScopeChat(chat_id=chat_id)}
            if chat_id is not None
            else {"language_code": language}
        )
        await self.bot.set_my_commands(
            [
                BotCommand(command=command, description=tr(labels, language))
                for command, labels in commands
            ],
            **options,
        )

    async def poll(self):
        while not self.stopping.is_set():
            try:
                updates = await self.bot.get_updates(
                    offset=self.state.offset(),
                    timeout=20,
                    allowed_updates=["message", "callback_query"],
                    request_timeout=30,
                )
                for update in updates:
                    if update.message and update.message.chat.type == "private":
                        self.state.enqueue(
                            update.update_id,
                            update.message.chat.id,
                            {
                                "type": "message",
                                "text": update.message.text,
                                "message_id": update.message.message_id,
                                "language_code": update.message.from_user.language_code
                                if update.message.from_user
                                else None,
                            },
                        )
                    elif update.callback_query and update.callback_query.message:
                        callback = update.callback_query
                        acknowledged = False
                        with contextlib.suppress(TelegramAPIError):
                            await self.bot.answer_callback_query(callback.id, request_timeout=5)
                            acknowledged = True
                        self.state.enqueue(
                            update.update_id,
                            callback.message.chat.id,
                            {
                                "type": "callback",
                                "data": callback.data,
                                "callback_id": callback.id,
                                "language_code": callback.from_user.language_code,
                                "acknowledged": acknowledged,
                            },
                        )
                    else:
                        self.state.advance(update.update_id)
                self.state.heartbeat()
            except TelegramConflictError:
                logger.error("Another polling instance is running; stopping this instance")
                self.stopping.set()
                return
            except TelegramRetryAfter as error:
                await asyncio.sleep(min(error.retry_after, 30))
            except (TelegramAPIError, OSError, TimeoutError) as error:
                logger.warning("poll_failed type=%s", type(error).__name__)
                await asyncio.sleep(2)

    async def prepare(self, job: dict) -> dict:
        payload = json.loads(job["payload"])
        chat_id = job["chat_id"]
        chat = self.state.chat(chat_id)
        pending = self.state.pending(chat_id)
        language = (
            chat["language"]
            if chat["language"] in {"uz", "ru"}
            else ("ru" if (payload.get("language_code") or "").startswith("ru") else "uz")
        )
        if payload["type"] == "callback":
            if not payload.get("acknowledged"):
                with contextlib.suppress(TelegramAPIError):
                    await self.bot.answer_callback_query(payload["callback_id"])
            action, _, key = (payload.get("data") or "").partition(":")
            if action == "lang" and key in {"uz", "ru", "auto"}:
                language = key if key in {"uz", "ru"} else language
                self.state.language(chat_id, language)
                with contextlib.suppress(TelegramAPIError):
                    await self.publish_commands(language, chat_id)
                return {
                    "texts": [ui_text("ready", language)],
                    "menu_at": 0,
                    "ui_language": language,
                }
            page = 0
            if action == "page":
                key, _, page_value = key.rpartition(":")
                if not page_value.isdecimal() or len(page_value) > 5:
                    return {"texts": [ui_text("expired", language)]}
                page = int(page_value)
            answer = self.state.answer_for(key, chat_id)
            if answer and answer.evidence and action == "page":
                if page > max((len(answer.evidence.rows) - 1) // 10, 0):
                    return {"texts": [ui_text("expired", language)]}
                return {
                    "texts": split_text(render_answer(answer, page)),
                    "answer": answer.model_dump(mode="json"),
                    "source_job_id": key,
                    "page": page,
                }
            if answer and answer.evidence and action == "sources":
                return {"texts": split_text(render_sources(answer.evidence, answer.language))}
            if answer and answer.evidence and action == "csv":
                return {
                    "texts": [],
                    "csv_answer": answer.model_dump(mode="json"),
                    "caption": csv_caption(answer),
                }
            return {"texts": [ui_text("expired", language)]}
        text = (payload.get("text") or "").strip()
        if not text:
            return {
                "texts": [ui_text("text_only", language)],
                "menu_at": 0,
                "ui_language": language,
            }
        command = text.split()[0].split("@")[0].lower()
        action = menu_action(text)
        if action:
            command = "/" + action
        if command == "/start":
            with contextlib.suppress(TelegramAPIError):
                await self.publish_commands(language, chat_id)
            if chat["language"] in {"uz", "ru"}:
                return {
                    "texts": [ui_text("intro", language) + "\n\n" + ui_text("ready", language)],
                    "menu_at": 0,
                    "ui_language": language,
                }
            return {
                "texts": [ui_text("intro", language), ui_text("choose_language", language)],
                "menu_at": 0,
                "language_keyboard": True,
                "ui_language": language,
            }
        if command in {"/help", "/examples", "/menu"}:
            return {
                "texts": [ui_text(command[1:], language)],
                "menu_at": 0,
                "ui_language": language,
            }
        if command == "/language":
            return {"texts": [ui_text("choose_language", language)], "language_keyboard": True}
        if command == "/reset":
            self.state.reset(chat_id)
            return {"texts": [ui_text("reset", language)], "menu_at": 0, "ui_language": language}
        if command.startswith("/"):
            return {"texts": [ui_text("help", language)], "menu_at": 0, "ui_language": language}
        if len(text) > 6000:
            return {"texts": [ui_text("shorten", language)]}
        hello = greeting(text)
        if hello:
            key, reply_language = hello
            return {"texts": [ui_text(key, reply_language)], "menu_at": 0, "ui_language": language}
        if export_followup(text) and pending is None:
            previous = self.state.latest_answer(chat_id)
            if previous and previous.evidence and previous.evidence.rows:
                return {
                    "texts": [],
                    "csv_answer": previous.model_dump(mode="json"),
                    "caption": csv_caption(previous),
                }
            clarification = Answer(
                outcome="clarify",
                language=guess_language(text),
                reason="missing_details",
                missing_fields=["reference"],
            )
            rendered = render_answer(clarification)
            self.state.set_pending(
                chat_id,
                {
                    "question": text,
                    "missing_fields": ["reference"],
                    "delivery": "csv",
                    "candidates": [],
                },
            )
            self.state.remember(chat_id, text, rendered)
            return {"texts": [rendered], "answer": clarification.model_dump(mode="json")}
        filename = requested_source_file(text) if file_preference(text) != "text" else None
        if filename:
            _, count, columns = await asyncio.to_thread(source_csv, self.engine.database, filename)
            reply_language = guess_language(text)
            caption = tr(
                (
                    f"{filename}\nQatorlar: {count}. Ustunlar: {columns}.",
                    f"{filename}\nСтрок: {count}. Столбцов: {columns}.",
                ),
                reply_language,
            )
            self.state.remember(chat_id, text, caption)
            self.state.set_pending(chat_id, None)
            return {"texts": [], "source_csv": filename, "caption": caption}
        pending = resolve_pending_reply(pending, text)
        latest = self.state.latest_result(chat_id)
        remaining = self.engine.settings.answer_timeout_seconds - (time.time() - job["received"])
        if remaining <= 1:
            answer = Answer(outcome="error", language=guess_language(text))
        else:
            typing = asyncio.create_task(self.typing(chat_id))
            try:
                async with asyncio.timeout(remaining):
                    answer = await self.engine.answer(
                        text, None, chat["history"], pending, latest["answer"] if latest else None
                    )
            except TimeoutError:
                answer = Answer(outcome="error", language=guess_language(text))
            finally:
                typing.cancel()
                await asyncio.gather(typing, return_exceptions=True)
        if answer.outcome == "about":
            return self.about_previous(chat_id, text, answer, latest)
        rendered = render_answer(answer)
        if answer.outcome != "error":
            self.state.remember(chat_id, text, memory_text(answer, rendered))
            if answer.outcome == "clarify":
                original = (
                    pending["question"] + "\nUser clarification: " + text
                    if pending and answer.continues_pending
                    else text
                )
                self.state.set_pending(
                    chat_id,
                    {
                        "question": original,
                        "missing_fields": answer.missing_fields,
                        "candidates": answer.candidates,
                        "delivery": file_preference(original),
                    },
                )
            else:
                self.state.set_pending(chat_id, None)
        result = {"texts": split_text(rendered), "answer": answer.model_dump(mode="json")}
        delivery_question = (
            pending["question"] + "\n" + text
            if pending and answer.continues_pending and file_preference(text) == "auto"
            else text
        )
        if (
            pending
            and answer.continues_pending
            and pending.get("delivery") == "csv"
            and file_preference(text) == "auto"
        ):
            delivery_question += " CSV formatida"
        if attach_csv(delivery_question, answer):
            result["attach_csv"] = True
            result["caption"] = csv_caption(answer)
        return result

    def about_previous(self, chat_id: int, text: str, answer: Answer, latest: dict) -> dict:
        self.state.set_pending(chat_id, None)
        stored = latest["answer"].model_copy(update={"language": answer.language})
        if answer.topic == "export":
            return {
                "texts": [],
                "csv_answer": stored.model_dump(mode="json"),
                "caption": csv_caption(stored),
            }
        if answer.topic == "next_page":
            page = latest["page"] + 1
            if page <= (len(stored.evidence.rows) - 1) // 10:
                self.state.remember(chat_id, text, f"Showed page {page + 1} of the stored result.")
                return {
                    "texts": split_text(render_answer(stored, page)),
                    "answer": stored.model_dump(mode="json"),
                    "source_job_id": latest["job_id"],
                    "page": page,
                }
            rendered = all_shown_text(stored)
        else:
            rendered = render_answer(answer)
        self.state.remember(chat_id, text, rendered)
        return {
            "texts": split_text(rendered),
            "answer": answer.model_copy(update={"evidence": None}).model_dump(mode="json"),
        }

    async def deliver(self, job: dict, result: dict):
        texts = result["texts"]
        answer = Answer.model_validate(result["answer"]) if result.get("answer") else None
        for index in range(job["next_part"], len(texts)):
            markup = None
            if result.get("menu_at") == index:
                markup = main_keyboard(result["ui_language"])
            if index == len(texts) - 1:
                if result.get("language_keyboard"):
                    markup = language_keyboard()
                elif answer and answer.evidence:
                    markup = pagination_keyboard(
                        result.get("source_job_id", job["id"]),
                        answer.language,
                        len(answer.evidence.rows),
                        result.get("page", 0),
                    )
            await self.bot.send_message(
                job["chat_id"], telegram_html(texts[index]), reply_markup=markup, parse_mode="HTML"
            )
            self.state.sent_part(job["id"], index + 1)
            if index < len(texts) - 1:
                await asyncio.sleep(1.05)
        if (result.get("csv_answer") or result.get("attach_csv")) and job["next_part"] <= len(
            texts
        ):
            csv_answer = Answer.model_validate(result.get("csv_answer") or result["answer"])
            await self.bot.send_document(
                job["chat_id"],
                BufferedInputFile(export_csv(csv_answer.evidence), filename="uzex21-result.csv"),
                caption=result.get("caption"),
            )
            self.state.sent_part(job["id"], len(texts) + 1)
        if result.get("source_csv") and job["next_part"] <= len(texts):
            contents, _, _ = await asyncio.to_thread(
                source_csv, self.engine.database, result["source_csv"]
            )
            await self.bot.send_document(
                job["chat_id"],
                BufferedInputFile(contents, filename=result["source_csv"]),
                caption=result.get("caption"),
            )
            self.state.sent_part(job["id"], len(texts) + 1)
        self.state.complete(job["id"])

    def job_language(self, job: dict) -> str:
        return guess_language(json.loads(job["payload"]).get("text") or "")

    def failure_result(self, job: dict) -> dict:
        answer = Answer(outcome="error", language=self.job_language(job))
        return {"texts": [error_text(answer.language)], "answer": answer.model_dump(mode="json")}

    async def process(self, job: dict):
        try:
            if job["result"]:
                result = json.loads(job["result"])
            else:
                try:
                    result = await self.prepare(job)
                except Exception as error:
                    logger.warning("prepare_failed id=%s type=%s", job["id"], type(error).__name__)
                    result = self.failure_result(job)
            self.state.save_result(job["id"], result)
            await self.deliver(job, result)
        except TelegramRetryAfter as error:
            self.state.retry(job["id"], error.retry_after + 1)
        except TelegramForbiddenError:
            self.state.retry(job["id"], 0, failed=True)
        except TelegramBadRequest:
            self.state.retry(job["id"], 0, failed=True)
            with contextlib.suppress(TelegramAPIError):
                await self.bot.send_message(job["chat_id"], error_text(self.job_language(job)))
        except Exception as error:
            logger.warning("job_failed id=%s type=%s", job["id"], type(error).__name__)
            self.state.retry(
                job["id"], min(2 ** (job["attempts"] + 1), 30), failed=job["attempts"] >= 4
            )

    async def worker(self):
        while not self.stopping.is_set():
            job = self.state.claim()
            if job is None:
                await asyncio.sleep(0.2)
                continue
            await self.process(job)


async def run_bot(settings: Settings):
    require_credentials(settings)
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    lock = settings.state_path.with_suffix(".lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        lock.close()
        raise RuntimeError("A bot process already owns this state directory") from error
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    state = State(settings.state_path)
    engine = Engine(settings)
    try:
        async with Bot(settings.telegram_bot_token.get_secret_value()) as bot:
            me = await bot.get_me()
            webhook = await bot.get_webhook_info()
            if webhook.url:
                raise RuntimeError("A webhook is configured; remove it before starting polling")
            service = Service(bot, state, engine)
            await service.publish_commands("uz")
            await service.publish_commands("ru")
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Boshlash / Начало"),
                    BotCommand(command="menu", description="Menyu / Меню"),
                    BotCommand(command="language", description="Til / Язык"),
                    BotCommand(command="help", description="Yordam / Помощь"),
                ]
            )
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, service.stopping.set)
            logger.info("bot_started username=%s", me.username)
            tasks = [asyncio.create_task(service.poll())] + [
                asyncio.create_task(service.worker())
                for _ in range(settings.max_concurrent_questions)
            ]
            await service.stopping.wait()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await engine.close()
        state.close()
        lock.close()
