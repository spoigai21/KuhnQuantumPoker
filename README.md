## Details

Kuhn poker is a simplified poker game (3 cards: Jack, Queen, King — one bet per hand). This project uses a 6-qubit quantum circuit, built with Qiskit, to discover a strong playing strategy through quantum optimization. You then play hands against that strategy in the browser.

Link: https://kuhn-quantum-poker.vercel.app
 
## How it works
 
1. **Quantum circuit (Qiskit):** A 6-qubit circuit with superposition and entanglement encodes the opponent's strategy. Each qubit's measurement probability maps to one decision (bet/call with each card).
2. **Optimization:** A classical optimizer (SciPy) tunes the circuit's gate angles to minimize how exploitable the strategy is.
3. **Gameplay:** The discovered probabilities drive the opponent's decisions as you play hands through the React frontend.
4. **Real hardware:** Click "Run on Real Hardware" to send the circuit to an actual IBM quantum processor via the IBM Quantum API and compare real results (with hardware noise) to the simulator.

## Tech stack
 
- **Quantum:** Qiskit, IBM Quantum API
- **Backend:** FastAPI, SciPy, NumPy
- **Frontend:** React (Vite)
- **Deployment:** Render (backend), Vercel (frontend)
