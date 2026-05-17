import { asNumber, asString, isRecord } from "../utils";
import { useAppContext } from "../store/context";

function formatConfidence(value: unknown): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return "待确认";
  return num <= 1 ? `${Math.round(num * 100)}%` : `${Math.round(num)}%`;
}

function getRecord(parent: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = parent[key];
  return isRecord(value) ? value : {};
}

function TradeStock({ stock }: { stock: Record<string, unknown> }) {
  const name = asString(stock.name || stock.symbol, "标的");
  const symbol = asString(stock.symbol);
  const entry = asString(stock.entry_price_range || stock.entry_price || stock.buy_price || "待触发");
  const stopLoss = asString(stock.stop_loss_price || stock.stop_loss || "待确认");
  const takeProfit = asString(stock.take_profit_price || stock.take_profit || "待确认");
  const position = asString(stock.suggested_position_pct || stock.position_pct || stock.position || "待确认");
  const trigger = asString(stock.monitoring_trigger || stock.trigger || stock.reason || "等待价格触发");

  return (
    <article className="trade-stock">
      <div className="trade-stock-title">
        <strong>{name}</strong>
        <span>{symbol}</span>
      </div>
      <dl>
        <div>
          <dt>入场区间</dt>
          <dd>{entry}</dd>
        </div>
        <div>
          <dt>止损</dt>
          <dd>{stopLoss}</dd>
        </div>
        <div>
          <dt>止盈</dt>
          <dd>{takeProfit}</dd>
        </div>
        <div>
          <dt>仓位</dt>
          <dd>{position}</dd>
        </div>
      </dl>
      <div className="trade-plan-note">{trigger}</div>
    </article>
  );
}

export function TradePlanPanel() {
  const { state } = useAppContext();
  if (!Object.keys(state.completeState).length) return null;

  const decision = getRecord(state.completeState, "final_decision");
  const tradePlan = getRecord(state.completeState, "trade_plan");
  const monitoredStocks = Array.isArray(tradePlan.monitored_stocks) ? tradePlan.monitored_stocks.filter(isRecord) : [];
  const action = asString(decision.action, "WAIT");
  const confidence = state.completeState.manager_confidence;
  const isBuy = action === "BUY" && monitoredStocks.length > 0;

  if (!isBuy) {
    return (
      <div className="trade-plan-panel compact">
        <div className="trade-plan-head">
          <strong>交易决策</strong>
          <span>{action}</span>
        </div>
        <p>{asString(decision.reasoning, "未生成交易决策展示。")}</p>
      </div>
    );
  }

  return (
    <div className="trade-plan-panel">
      <div className="trade-plan-head">
        <strong>交易决策</strong>
        <span>
          决策 {action} · 置信度 {formatConfidence(confidence)} · 资金 {asNumber(state.completeState.capital, state.capital).toLocaleString("zh-CN")}
        </span>
      </div>
      <div className="trade-plan-reason">{asString(decision.reasoning)}</div>
      <div className="trade-plan-table">
        {monitoredStocks.map((stock, index) => (
          <TradeStock key={`${asString(stock.symbol, "stock")}-${index}`} stock={stock} />
        ))}
      </div>
      <div className="trade-plan-note">{asString(tradePlan.position_sizing_rationale)}</div>
    </div>
  );
}
