import type { SourceItem } from "../store/types";

function SourceRow({ item }: { item: SourceItem }) {
  const success = item.status === "success";
  const statusText = success ? "接通成功" : "接通失败";

  return (
    <article className={`source-row ${success ? "success" : "failed"}`}>
      <span className="source-status-dot" />
      <div className="source-main">
        <div className="source-row-head">
          <strong>{item.site || item.label || "未知来源"}</strong>
          <span>{statusText}</span>
        </div>
        {item.data && <div className="source-data">{item.data}</div>}
        {item.url && /^https?:\/\//.test(item.url) && (
          <a className="source-link" href={item.url} target="_blank" rel="noreferrer">
            {item.url}
          </a>
        )}
        {(item.message || item.detail) && <div className="source-detail">{item.message || item.detail}</div>}
      </div>
    </article>
  );
}

export function SourceList({ sources }: { sources: SourceItem[] }) {
  if (!sources.length) {
    return <div className="source-empty">运行后显示浏览的网站、获取的数据和接通状态。</div>;
  }
  return (
    <>
      {sources.map((item, index) => (
        <SourceRow key={`${item.label}-${index}`} item={item} />
      ))}
    </>
  );
}
