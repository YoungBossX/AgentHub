// Decode the filesystem ID syntax used by Vite, before applying path policy.
export function previewFileId(id) {
  let value = id.split("?")[0].split("#")[0];
  if (value.startsWith("/@fs/")) {
    value = value.slice(5);
    // Vite joins /@fs/ and /home/... into /@fs/home/.... Restore the
    // POSIX root instead of interpreting it relative to the preview directory.
    if (!value.startsWith("/") && !/^[A-Za-z]:[\\/]/.test(value)) value = "/" + value;
  }
  if (process.platform === "win32" && /^\/[A-Za-z]:\//.test(value)) value = value.slice(1);
  return value;
}
