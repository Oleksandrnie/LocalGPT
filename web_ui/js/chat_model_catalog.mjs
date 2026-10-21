function modelId(item) {
  // Ollama inventory records use `id` for the digest and `name` for the
  // selectable model tag. Prefer the tag so catalog entries deduplicate and
  // custom models never appear under their digest.
  return String(item?.name || item?.id || "").trim();
}

export function buildSelectableChatModels(catalog, excludedCatalogs, installedModels) {
  const chatCatalog = (Array.isArray(catalog) ? catalog : []).filter((item) => modelId(item));
  const excludedIds = new Set(
    (Array.isArray(excludedCatalogs) ? excludedCatalogs : [])
      .map(modelId)
      .filter(Boolean),
  );
  const knownIds = new Set([...chatCatalog.map(modelId), ...excludedIds]);
  const customInstalled = (Array.isArray(installedModels) ? installedModels : [])
    .filter((item) => {
      const name = modelId(item);
      if (!name || knownIds.has(name)) return false;
      const capabilities = Array.isArray(item?.capabilities)
        ? item.capabilities.map((value) => String(value || "").trim().toLowerCase())
        : [];
      const textCapable = capabilities.some((value) => ["text", "completion", "chat"].includes(value));
      return !(capabilities.includes("embedding") && !textCapable);
    })
    .map((item) => {
      const name = modelId(item);
      knownIds.add(name);
      return {
        ...item,
        id: name,
        name,
        title: name,
        category: "installed_custom",
        weight: "local",
        recommended: false,
        experimental: false,
        custom_installed: true,
        description: "Установлена локально в Ollama и отсутствует в каталоге LocalGPT.",
      };
    });
  return [...chatCatalog, ...customInstalled];
}
