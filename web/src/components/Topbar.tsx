import { useHealth } from "../hooks/useHealth";

export function Topbar() {
  const health = useHealth();

  return (
    <header className="topbar">
      <div className="brand-block">
        <div className="brand-mark">M</div>
        <div>
          <div className="eyebrow">Multi-Agent Investment</div>
          <h1>股票决策工作台</h1>
        </div>
      </div>
      <nav className="topnav" aria-label="工作台导航">
        <a href="#control-panel">参数</a>
        <a href="#process-panel">流程</a>
        <a href="#result-panel">输出</a>
      </nav>
      <div className="topbar-right">
        <div className={`health ${health.status}`}>
          <span className="dot" />
          <span>{health.text}</span>
        </div>
      </div>
    </header>
  );
}
