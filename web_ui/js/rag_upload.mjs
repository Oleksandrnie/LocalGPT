const labels = {
  unsupported_file_type: "Неподдерживаемый формат. Поддерживаются .md и HTML-выгрузки Telegram.",
  file_too_large: "Markdown-файл превышает лимит 5 MiB.",
  file_write_failed: "Не удалось сохранить файл в папку профиля. Проверьте доступ к папке и свободное место на диске.",
  file_name_missing: "Не передано имя файла.",
  telegram_history_not_found: "В HTML не найден контейнер истории Telegram (.history).",
  telegram_header_not_found: "В HTML не найден заголовок выгрузки Telegram (.page_header).",
  telegram_messages_not_found: "В истории HTML не найдено завершённых блоков сообщений Telegram.",
  telegram_duplicate_message_ids: "В HTML повторяются ID сообщений.",
  telegram_incomplete_message: "В HTML обнаружен незакрытый блок сообщения. Возможно, экспорт сохранён не полностью.",
  telegram_encoding_error: "HTML не удалось прочитать как UTF-8. Проверьте кодировку экспорта.",
  telegram_html_nesting_error: "В HTML слишком глубокая вложенность блоков.",
  invalid_telegram_html: "HTML не удалось разобрать как выгрузку Telegram.",
  telegram_requires_local_model_endpoint: "Для Telegram выберите локальный endpoint модели.",
  telegram_requires_local_hash_embeddings: "Для Telegram требуется локальный хешевый embedding-provider.",
};

export function describeRagUploadError(error = {}) {
  const code = String(error.code || error.error || "unknown_upload_error");
  const reason = labels[code] || String(error.message || error.error || "Неизвестная ошибка загрузки.");
  const file = error.file ? `${error.file}: ` : "";
  return `${file}${reason}\nКод: ${code}`;
}

export function ragUploadReport(result = {}) {
  const count = Array.isArray(result.saved) ? result.saved.length : 0;
  const errors = Array.isArray(result.errors) ? result.errors : [];
  const summary = count
    ? `RAG: добавлено файлов ${count}${errors.length ? `, ошибок ${errors.length}` : ""}. Теперь можно индексировать.`
    : `RAG: файлы не добавлены${errors.length ? `, ошибок ${errors.length}` : ""}.`;
  return {
    summary,
    tone: errors.length ? (count ? "warning" : "error") : (count ? "success" : "warning"),
    details: [summary, ...errors.map(describeRagUploadError)].join("\n\n"),
  };
}
