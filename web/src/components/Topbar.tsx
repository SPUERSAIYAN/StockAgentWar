import { useHealth } from "../hooks/useHealth";

export function Topbar() {
  const health = useHealth();

  return (
    <header className="topbar">
      <div>
        <div className="eyebrow">AI Investment Console</div>
        <h1>股票决策工作台</h1>
      </div>
      <div className="topbar-right">
        <div className={`health ${health.status}`}>
          <span className="dot" />
          <span>{health.text}</span>
        </div>
      </div>
    </header>
  );
}
