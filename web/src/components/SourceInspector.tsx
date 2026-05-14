import { useState } from "react";
import type { SourceItem } from "../store/types";
import { SourceList } from "./SourceList";

export function SourceInspector({ sources }: { sources: SourceItem[] }) {
  const [expanded, setExpanded] = useState(false);
  const successCount = sources.filter((item) => item.status === "success").length;
  const failedCount = sources.filter((item) => item.status === "failed").length;
  const hasData = sources.length > 0;
  const className = `source-inspector${hasData ? " has-data" : ""}${failedCount ? " has-failure" : ""}`;
  const summary = hasData ? `${successCount} 成功 / ${failedCount} 失败` : "等待接通";

  return (
    <div className={className} data-source-node="information_analysis">
      <button className="source-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
        <span className="source-toggle-title">浏览来源与数据</span>
        <strong className="source-toggle-summary">{summary}</strong>
      </button>
      <div className="source-list" hidden={!expanded}>
        <SourceList sources={sources} />
      </div>
    </div>
  );
}
