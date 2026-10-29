const labels = {
  rag_upload_file_count_exceeded: "Сервер отклонил количество файлов в запросе.",
  rag_upload_total_bytes_exceeded: "Суммарный размер Markdown-файлов в запросе превышает лимит 20 MiB.",
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
  const remaining = Number(result.not_processed) || 0;
  const completeSummary = summary + (remaining ? ` Не подтверждена загрузка файлов: ${remaining}; ранее добавленные сохранены.` : "");
  return {
    summary: completeSummary,
    tone: errors.length ? (count ? "warning" : "error") : (count ? "success" : "warning"),
    details: [completeSummary, ...errors.map(describeRagUploadError)].join("\n\n"),
  };
}

// Bound each HTTP request while allowing an arbitrary-size selection in the UI.
export function splitRagUpload(files, maxFiles = 12, maxBytes = 20 * 1024 * 1024) {
  const batches = [];
  let batch = [], bytes = 0;
  for (const file of Array.from(files || [])) {
    const size = Math.max(0, Number(file.size) || 0);
    if (batch.length && (batch.length >= maxFiles || bytes + size > maxBytes)) {
      batches.push(batch);
      batch = []; bytes = 0;
    }
    batch.push(file); bytes += size;
  }
  if (batch.length) batches.push(batch);
  return batches;
}

export async function uploadRagBatches(files, sendBatch, { onProgress, onFileError, onBatchError } = {}) {
  const selection = Array.from(files || []);
  const batches = splitRagUpload(selection);
  const result = { saved: [], errors: [], processed: 0, total: selection.length, not_processed: 0 };
  onProgress?.(result);
  for (const batch of batches) {
    let response;
    try {
      response = await sendBatch(batch);
    } catch (error) {
      onBatchError?.(error);
      result.errors.push({ code: error.code || 'rag_upload_request_failed', message: error.message || 'Ошибка запроса загрузки' });
      result.not_processed = selection.length - result.processed;
      break;
    }
    result.saved.push(...(Array.isArray(response?.saved) ? response.saved : []));
    const errors = Array.isArray(response?.errors) ? response.errors : [];
    result.errors.push(...errors);
    for (const error of errors) onFileError?.(error);
    result.processed += batch.length;
    result.status = response?.status || result.status;
    onProgress?.(result);
  }
  return result;
}
