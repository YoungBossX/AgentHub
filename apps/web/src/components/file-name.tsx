// The visible prefix may shrink; the tail retains whole graphemes and extensions.
export function FileName({ path }: { path: string }) {
  const basename = path.split(/[\\/]/).at(-1) ?? path
  const extension = basename.match(/(?:\.d\.[cm]?ts|\.tar\.(?:gz|bz2|xz|zst))$/i)?.[0]
    ?? (basename.lastIndexOf(".") > 0 ? basename.slice(basename.lastIndexOf(".")) : "")
  const stem = extension ? path.slice(0, -extension.length) : path
  const graphemes = Array.from(new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(stem), part => part.segment)
  const suffix = graphemes.slice(-8).join("") + extension
  const prefix = path.slice(0, -suffix.length)
  if (!prefix) return <span className="file-name" title={path} aria-label={path}>{path}</span>
  return <span className="file-name" title={path} aria-label={path}>
    <span className="filename-prefix" aria-hidden="true">{prefix}</span>
    <span className="filename-suffix" aria-hidden="true">{suffix}</span>
  </span>
}
