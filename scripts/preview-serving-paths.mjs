import { parse as parseUrl } from "node:url";

// Match Connect/parseurl's legacy parser, including nonstandard protocol forms.
// WHATWG URL would normalize these differently before the downstream route.
// With slashesDenoteHost left false, origin-form // paths remain paths.
export function previewRequestPath(url = "/") {
  return decodeURIComponent(parseUrl(url).pathname ?? "/");
}

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
