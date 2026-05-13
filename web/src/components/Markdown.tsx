import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownProps {
  text: string;
  className?: string;
  emptyText?: string;
}

export function Markdown({ text, className = "", emptyText = "等待输出。" }: MarkdownProps) {
  const raw = String(text || "");
  const isEmpty = !raw.trim();

  return (
    <div className={`${className} markdown${isEmpty ? " empty" : ""}`}>
      {isEmpty ? (
        emptyText
      ) : (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
          }}
        >
          {raw}
        </ReactMarkdown>
      )}
    </div>
  );
}
