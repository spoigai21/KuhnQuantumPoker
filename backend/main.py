"""
Kuhn Poker — FastAPI Backend
=============================
On startup: a quantum circuit + optimizer discovers the Quantum opponent's best strategy.
Then: API endpoints let a React frontend play hands against that AI.

Run:  uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import uuid
import os

from dotenv import load_dotenv
load_dotenv()  # reads .env file automatically

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from scipy.optimize import minimize

# ────────────────────────────────────────────────
# GAME ENGINE
# ────────────────────────────────────────────────

CARDS = {0: "J", 1: "Q", 2: "K"}


def expected_value(p1_bet, p1_call, p2_bet, p2_call):
    """Player 1's exact expected payoff per hand."""
    total = 0.0
    for c1 in range(3):
        for c2 in range(3):
            if c1 == c2:
                continue
            win = 1 if c1 > c2 else -1
            total += p1_bet[c1] * (
                p2_call[c2] * 2 * win + (1 - p2_call[c2]) * 1
            )
            total += (1 - p1_bet[c1]) * (
                p2_bet[c2] * (p1_call[c1] * 2 * win + (1 - p1_call[c1]) * -1)
                + (1 - p2_bet[c2]) * win
            )
    return total / 6.0


# ────────────────────────────────────────────────
# QUANTUM SOLVER  (runs once at startup)
# ────────────────────────────────────────────────

def build_circuit(params):
    """
    6-qubit circuit with superposition and entanglement.
    - Hadamard gates: put all qubits in superposition
    - CNOT gates: entangle qubits so decisions are correlated
    - RY rotations: tunable parameters the optimizer adjusts
    """
    qc = QuantumCircuit(6)

    # Superposition: all qubits start in equal mix of 0 and 1
    for i in range(6):
        qc.h(i)

    # Layer 1: parameterized rotations
    for i in range(6):
        qc.ry(params[i], i)

    # Entanglement: link qubits together
    for i in range(5):
        qc.cx(i, i + 1)

    # Layer 2: more rotations after entanglement
    for i in range(6):
        qc.ry(params[6 + i], i)

    return qc


def circuit_to_strategy(params):
    """Run circuit → extract 6 probabilities → split into bet & call arrays."""
    qc = build_circuit(params)
    sv = Statevector.from_instruction(qc)
    probs = [sv.probabilities([i])[1] for i in range(6)]
    # qubits 0-2: P2 bet probs [J, Q, K]
    # qubits 3-5: P2 call probs [J, Q, K]
    return probs[0:3], probs[3:6]


def cost_function(params):
    """
    How badly can the best opponent exploit this Quantum opponent strategy?
    Lower = harder to beat. The optimizer minimizes this.
    """
    p2_bet, p2_call = circuit_to_strategy(params)

    best_p1_ev = -999.0
    for bits in range(64):
        b = [float((bits >> i) & 1) for i in range(3)]
        c = [float((bits >> (i + 3)) & 1) for i in range(3)]
        ev = expected_value(b, c, p2_bet, p2_call)
        best_p1_ev = max(best_p1_ev, ev)

    return best_p1_ev


def solve_ai_strategy():
    """Find the Quantum opponent strategy that's hardest to beat."""
    print("⚛  Running quantum optimizer to find Quantum opponent strategy...")
    best_result = None
    for attempt in range(5):
        x0 = np.random.default_rng(attempt).uniform(-np.pi, np.pi, 12)
        result = minimize(
            cost_function,
            x0,
            method="COBYLA",
            options={"maxiter": 2000, "rhobeg": 0.5},
        )
        if best_result is None or result.fun < best_result.fun:
            best_result = result
        print(f"   Attempt {attempt+1}: weakness = {result.fun:.6f}")
    result = best_result
    p2_bet, p2_call = circuit_to_strategy(result.x)
    print(f"   Weakness: {result.fun:.6f}")
    print(f"   Opponent bet probs:  J={p2_bet[0]:.3f}  Q={p2_bet[1]:.3f}  K={p2_bet[2]:.3f}")
    print(f"   Opponent call probs: J={p2_call[0]:.3f}  Q={p2_call[1]:.3f}  K={p2_call[2]:.3f}")
    print("⚛  Quantum opponent ready.\n")
    return p2_bet, p2_call, result.x.tolist()


# ────────────────────────────────────────────────
# FASTAPI APP
# ────────────────────────────────────────────────

app = FastAPI(title="Kuhn Poker Quantum Opponent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pre-computed by quantum optimizer (superposition + entanglement circuit)
QO_BET = [0.2859, 0.3136, 0.8578]
QO_CALL = [0.1306, 0.4666, 0.9250]
QO_PARAMS = [-0.3799, -1.0883, -2.4736, -2.6528, 3.0709, 3.2555, -0.1422, 1.5444, 1.719, 5.405, 3.2022, -1.0258]

# In-memory game storage
games: dict = {}
stats = {"hands_played": 0, "player_wins": 0, "opponent_wins": 0, "player_chips": 0}

rng = np.random.default_rng()


class ActionRequest(BaseModel):
    action: str  # "bet", "check", "call", "fold"


def opponent_decides_bet(card: int) -> bool:
    """Should the AI bet? Based on quantum-found probabilities."""
    return rng.random() < QO_BET[card]


def opponent_decides_call(card: int) -> bool:
    """Should the AI call? Based on quantum-found probabilities."""
    return rng.random() < QO_CALL[card]


def finish_game(game: dict, winner: str, pot: int):
    """End the hand and update stats."""
    game["status"] = "finished"
    game["winner"] = winner

    if winner == "player":
        game["payout"] = pot // 2  # net gain (pot includes player's own chips)
        stats["player_wins"] += 1
        stats["player_chips"] += game["payout"]
    elif winner == "opponent":
        game["payout"] = -(pot // 2)
        stats["opponent_wins"] += 1
        stats["player_chips"] += game["payout"]
    else:  # shouldn't happen in Kuhn but just in case
        game["payout"] = 0

    stats["hands_played"] += 1
    game["opponent_card"] = CARDS[game["opponent_card_idx"]]  # reveal Quantum opponent's card


@app.post("/game/new")
def new_game():
    """Deal a new hand. Player is P1 (acts first)."""
    cards = rng.choice(3, size=2, replace=False)
    game_id = str(uuid.uuid4())[:8]

    game = {
        "id": game_id,
        "player_card_idx": int(cards[0]),
        "opponent_card_idx": int(cards[1]),
        "player_card": CARDS[int(cards[0])],
        "opponent_card": "?",  # hidden until hand ends
        "pot": 2,
        "status": "player_turn",  # player bets or checks
        "actions": [],
        "winner": None,
        "payout": 0,
        "message": "Your turn: bet or check?",
    }
    games[game_id] = game

    return {k: v for k, v in game.items() if k != "player_card_idx" and k != "opponent_card_idx"}


@app.post("/game/{game_id}/action")
def player_action(game_id: str, req: ActionRequest):
    """Player makes a move. AI responds."""
    if game_id not in games:
        raise HTTPException(404, "Game not found")

    game = games[game_id]
    if game["status"] == "finished":
        raise HTTPException(400, "Hand is over. Start a new game.")

    action = req.action.lower()
    pc = game["player_card_idx"]
    ac = game["opponent_card_idx"]
    player_wins_showdown = pc > ac

    # ── Player's first action ──
    if game["status"] == "player_turn":
        if action == "bet":
            game["actions"].append("player_bet")
            game["pot"] += 1  # player adds 1

            # AI decides: call or fold?
            if opponent_decides_call(ac):
                game["actions"].append("ai_call")
                game["pot"] += 1
                winner = "player" if player_wins_showdown else "opponent"
                game["message"] = f"Opponent calls. {'You win!' if winner == 'player' else 'Opponent wins.'} (showdown)"
                finish_game(game, winner, game["pot"])
            else:
                game["actions"].append("ai_fold")
                game["message"] = "Opponent folds. You win the pot!"
                finish_game(game, "player", game["pot"])

        elif action == "check":
            game["actions"].append("player_check")

            # AI decides: bet or check?
            if opponent_decides_bet(ac):
                game["actions"].append("ai_bet")
                game["pot"] += 1
                game["status"] = "player_respond"
                game["message"] = "Opponent bets. Call or fold?"
            else:
                game["actions"].append("ai_check")
                winner = "player" if player_wins_showdown else "opponent"
                game["message"] = f"Opponent checks. {'You win!' if winner == 'player' else 'Opponent wins.'} (showdown)"
                finish_game(game, winner, game["pot"])
        else:
            raise HTTPException(400, "Invalid action. Use 'bet' or 'check'.")

    # ── Player responds to Quantum opponent's bet ──
    elif game["status"] == "player_respond":
        if action == "call":
            game["actions"].append("player_call")
            game["pot"] += 1
            winner = "player" if player_wins_showdown else "opponent"
            game["message"] = f"You call. {'You win!' if winner == 'player' else 'Opponent wins.'} (showdown)"
            finish_game(game, winner, game["pot"])

        elif action == "fold":
            game["actions"].append("player_fold")
            game["message"] = "You fold. Opponent wins the pot."
            finish_game(game, "opponent", game["pot"])
        else:
            raise HTTPException(400, "Invalid action. Use 'call' or 'fold'.")

    return {k: v for k, v in game.items() if k != "player_card_idx" and k != "opponent_card_idx"}


@app.get("/game/{game_id}")
def get_game(game_id: str):
    """Get current game state."""
    if game_id not in games:
        raise HTTPException(404, "Game not found")
    game = games[game_id]
    return {k: v for k, v in game.items() if k != "player_card_idx" and k != "opponent_card_idx"}


@app.get("/stats")
def get_stats():
    """Overall win/loss record."""
    return stats


@app.get("/ai/strategy")
def get_ai_strategy():
    """Peek at the Quantum opponent's quantum-discovered strategy (for debugging/display)."""
    return {
        "bet_probs": {"J": round(QO_BET[0], 4), "Q": round(QO_BET[1], 4), "K": round(QO_BET[2], 4)},
        "call_probs": {"J": round(QO_CALL[0], 4), "Q": round(QO_CALL[1], 4), "K": round(QO_CALL[2], 4)},
        "circuit_params": [round(p, 4) for p in QO_PARAMS],
    }


# ────────────────────────────────────────────────
# REAL QUANTUM HARDWARE
# ────────────────────────────────────────────────

class TokenRequest(BaseModel):
    token: str


@app.post("/ai/set-token")
def set_ibm_token(req: TokenRequest):
    """Save your IBM Quantum token (get one free at quantum.ibm.com)."""
    os.environ["IBM_QUANTUM_TOKEN"] = req.token
    return {"status": "ok", "message": "Token saved. You can now use /ai/verify."}


@app.post("/ai/verify")
def verify_on_real_hardware():
    """
    Run the Quantum opponent's circuit on a REAL IBM quantum processor.
    Compares real hardware results to the simulator.
    Requires IBM_QUANTUM_TOKEN env variable.
    """
    token = os.environ.get("IBM_QUANTUM_TOKEN")
    if not token:
        raise HTTPException(
            400,
            "No IBM token set. POST your token to /ai/set-token first, "
            "or set IBM_QUANTUM_TOKEN env variable. "
            "Get a free token at https://quantum.ibm.com",
        )

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    except ImportError:
        raise HTTPException(
            500,
            "qiskit-ibm-runtime not installed. Run: pip install qiskit-ibm-runtime",
        )

    # Build the circuit with measurements
    qc = build_circuit(QO_PARAMS)
    qc.measure_all()

    # Connect to IBM Quantum
    service = QiskitRuntimeService(token=token)
    backend = service.least_busy(operational=True, simulator=False)

    # Transpile for the real hardware
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa_circuit = pm.run(qc)

    # Run on real quantum hardware
    sampler = Sampler(mode=backend)
    sampler.options.default_shots = 4096
    job = sampler.run([isa_circuit])
    result = job.result()[0]
    counts = result.data.meas.get_counts()

    # Extract marginal probabilities from real hardware
    total_shots = sum(counts.values())
    real_probs = []
    for i in range(6):
        p = sum(v for k, v in counts.items() if k[-(i + 1)] == "1") / total_shots
        real_probs.append(round(p, 4))

    # Simulator comparison
    sim_bet, sim_call = circuit_to_strategy(QO_PARAMS)

    return {
        "backend": backend.name,
        "shots": total_shots,
        "job_id": job.job_id(),
        "real_hardware": {
            "bet_probs": {"J": real_probs[0], "Q": real_probs[1], "K": real_probs[2]},
            "call_probs": {"J": real_probs[3], "Q": real_probs[4], "K": real_probs[5]},
        },
        "simulator": {
            "bet_probs": {"J": round(sim_bet[0], 4), "Q": round(sim_bet[1], 4), "K": round(sim_bet[2], 4)},
            "call_probs": {"J": round(sim_call[0], 4), "Q": round(sim_call[1], 4), "K": round(sim_call[2], 4)},
        },
        "message": f"Circuit ran on {backend.name}. Compare real vs simulator above — "
                   "differences are quantum noise from the real chip.",
    }