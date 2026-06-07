import { useState, useEffect, useCallback } from "react";
import "./App.css";

const API = "https://kuhnquantumpoker.onrender.com";

const CARD_DISPLAY = {
  J: { label: "J", name: "Jack", rank: 1 },
  Q: { label: "Q", name: "Queen", rank: 2 },
  K: { label: "K", name: "King", rank: 3 },
  "?": { label: "?", name: "Hidden", rank: 0 },
};

function Card({ card, hidden = false, label }) {
  const info = CARD_DISPLAY[card] || CARD_DISPLAY["?"];
  return (
    <div className={`card ${hidden ? "card-hidden" : ""}`}>
      <span className="card-label">{label}</span>
      <span className="card-value">{hidden ? "?" : info.label}</span>
      <span className="card-name">{hidden ? "Hidden" : info.name}</span>
    </div>
  );
}

export default function App() {
  const [game, setGame] = useState(null);
  const [stats, setStats] = useState({ hands_played: 0, player_wins: 0, opponent_wins: 0, player_chips: 0 });
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [strategy, setStrategy] = useState(null);
  const [showStrategy, setShowStrategy] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/stats`);
      setStats(await res.json());
    } catch (e) {
      console.error("Failed to fetch stats", e);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  async function newGame() {
    setLoading(true);
    setVerifyResult(null);
    try {
      const res = await fetch(`${API}/game/new`, { method: "POST" });
      const data = await res.json();
      setGame(data);
    } catch (e) {
      console.error("Failed to start game", e);
    }
    setLoading(false);
  }

  async function doAction(action) {
    if (!game) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/game/${game.id}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();
      setGame(data);
      if (data.status === "finished") {
        fetchStats();
      }
    } catch (e) {
      console.error("Action failed", e);
    }
    setLoading(false);
  }

  async function verifyReal() {
    setVerifying(true);
    try {
      const res = await fetch(`${API}/ai/verify`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        setVerifyResult({ error: err.detail });
      } else {
        setVerifyResult(await res.json());
      }
    } catch (e) {
      setVerifyResult({ error: "Failed to connect to server" });
    }
    setVerifying(false);
  }

  async function loadStrategy() {
    try {
      const res = await fetch(`${API}/ai/strategy`);
      setStrategy(await res.json());
      setShowStrategy(!showStrategy);
    } catch (e) {
      console.error("Failed to load strategy", e);
    }
  }

  const isFinished = game?.status === "finished";
  const needsResponse = game?.status === "player_respond";
  const isPlayerTurn = game?.status === "player_turn";

  return (
    <div className="app">
      <header className="header">
        <h1>Kuhn Poker</h1>
        <p className="subtitle">vs Quantum Opponent</p>
      </header>

      {/* Stats Bar */}
      <div className="stats-bar">
        <div className="stat">
          <span className="stat-num">{stats.hands_played}</span>
          <span className="stat-label">Hands</span>
        </div>
        <div className="stat">
          <span className="stat-num wins">{stats.player_wins}</span>
          <span className="stat-label">Wins</span>
        </div>
        <div className="stat">
          <span className="stat-num losses">{stats.opponent_wins}</span>
          <span className="stat-label">Losses</span>
        </div>
        <div className="stat">
          <span className={`stat-num ${stats.player_chips >= 0 ? "wins" : "losses"}`}>
            {stats.player_chips >= 0 ? "+" : ""}{stats.player_chips}
          </span>
          <span className="stat-label">Chips</span>
        </div>
      </div>

      {/* Game Area */}
      <div className="table">
        {!game ? (
          <div className="start-screen">
            <p>3 cards. 2 players. 1 bet.</p>
            <p className="rules">
              Jack &lt; Queen &lt; King. You act first — bet or check.
              The quantum opponent's strategy was discovered by a quantum circuit.
            </p>
            <button className="btn btn-deal" onClick={newGame} disabled={loading}>
              Deal
            </button>
          </div>
        ) : (
          <>
            {/* Cards */}
            <div className="cards">
              <Card card={game.player_card} label="You" />
              <div className="vs">vs</div>
              <Card
                card={isFinished ? game.opponent_card : "?"}
                hidden={!isFinished}
                label="Opponent"
              />
            </div>

            {/* Pot */}
            <div className="pot">
              Pot: <strong>{game.pot}</strong> chips
            </div>

            {/* Action History */}
            {game.actions.length > 0 && (
              <div className="history">
                {game.actions.map((a, i) => (
                  <span key={i} className={`action-tag ${a.startsWith("player") ? "player-action" : "opponent-action"}`}>
                    {a.replace("player_", "You: ").replace("opponent_", "Opp: ")}
                  </span>
                ))}
              </div>
            )}

            {/* Message */}
            <div className={`message ${isFinished ? (game.winner === "player" ? "msg-win" : "msg-lose") : ""}`}>
              {game.message}
              {isFinished && (
                <span className="payout">
                  {game.payout > 0 ? ` (+${game.payout} chips)` : ` (${game.payout} chips)`}
                </span>
              )}
            </div>

            {/* Action Buttons */}
            <div className="actions">
              {isPlayerTurn && (
                <>
                  <button className="btn btn-bet" onClick={() => doAction("bet")} disabled={loading}>
                    Bet
                  </button>
                  <button className="btn btn-check" onClick={() => doAction("check")} disabled={loading}>
                    Check
                  </button>
                </>
              )}
              {needsResponse && (
                <>
                  <button className="btn btn-bet" onClick={() => doAction("call")} disabled={loading}>
                    Call
                  </button>
                  <button className="btn btn-check" onClick={() => doAction("fold")} disabled={loading}>
                    Fold
                  </button>
                </>
              )}
              {isFinished && (
                <button className="btn btn-deal" onClick={newGame} disabled={loading}>
                  Next Hand
                </button>
              )}
            </div>
          </>
        )}
      </div>

      {/* Bottom Controls */}
      <div className="controls">
        <button className="btn-link" onClick={loadStrategy}>
          {showStrategy ? "Hide" : "Show"} Quantum Strategy
        </button>
        <button
          className="btn-link"
          onClick={verifyReal}
          disabled={verifying}
        >
          {verifying ? "Running on IBM..." : "Run on Real Hardware"}
        </button>
      </div>

      {/* Strategy Display */}
      {showStrategy && strategy && (
        <div className="strategy-panel">
          <h3>Quantum-Discovered Strategy</h3>
          <p>These probabilities were found by optimizing a 6-qubit quantum circuit:</p>
          <div className="strat-grid">
            <div>
              <strong>Bet probability</strong>
              <div>Jack: {(strategy.bet_probs.J * 100).toFixed(1)}%</div>
              <div>Queen: {(strategy.bet_probs.Q * 100).toFixed(1)}%</div>
              <div>King: {(strategy.bet_probs.K * 100).toFixed(1)}%</div>
            </div>
            <div>
              <strong>Call probability</strong>
              <div>Jack: {(strategy.call_probs.J * 100).toFixed(1)}%</div>
              <div>Queen: {(strategy.call_probs.Q * 100).toFixed(1)}%</div>
              <div>King: {(strategy.call_probs.K * 100).toFixed(1)}%</div>
            </div>
          </div>
          <p className="strat-note">
            Circuit params: [{strategy.circuit_params.map((p) => p.toFixed(3)).join(", ")}]
          </p>
        </div>
      )}

      {/* Verify Result */}
      {verifyResult && (
        <div className="verify-panel">
          {verifyResult.error ? (
            <p className="verify-error">{verifyResult.error}</p>
          ) : (
            <>
              <h3>Real Quantum Hardware Results</h3>
              <p>
                Ran on <strong>{verifyResult.backend}</strong> ({verifyResult.shots} shots)
              </p>
              <div className="compare-grid">
                <div>
                  <strong>Simulator</strong>
                  <div>Bet: J={verifyResult.simulator.bet_probs.J} Q={verifyResult.simulator.bet_probs.Q} K={verifyResult.simulator.bet_probs.K}</div>
                  <div>Call: J={verifyResult.simulator.call_probs.J} Q={verifyResult.simulator.call_probs.Q} K={verifyResult.simulator.call_probs.K}</div>
                </div>
                <div>
                  <strong>Real chip</strong>
                  <div>Bet: J={verifyResult.real_hardware.bet_probs.J} Q={verifyResult.real_hardware.bet_probs.Q} K={verifyResult.real_hardware.bet_probs.K}</div>
                  <div>Call: J={verifyResult.real_hardware.call_probs.J} Q={verifyResult.real_hardware.call_probs.Q} K={verifyResult.real_hardware.call_probs.K}</div>
                </div>
              </div>
              <p className="verify-note">
                Differences are quantum noise from the physical chip. Job ID: {verifyResult.job_id}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
