from Agent import Agent, AgentGreedy
from WarehouseEnv import WarehouseEnv, manhattan_distance
import random
import time


# ==================================================================================
#                                Global Helper Functions
# ==================================================================================

# ------------------------ Distance & Cost Calculations -------------------------

# Calculates the theoretical reward for delivering a specific package
def get_reward(package) -> float:
    return 2 * manhattan_distance(package.position, package.destination)


# Calculates the number of steps required to deliver a package.
# Handles two cases:
# 1. Robot is already carrying the package.
# 2. Robot needs to go pick up the package first.
def get_cost(robot, package) -> int:
    if robot.package is package:
        return manhattan_distance(robot.position, package.destination) + 1
    else:
        return (manhattan_distance(robot.position, package.position) +
                manhattan_distance(package.position, package.destination) + 2)


# Finds the distance to the nearest charging station
def get_min_charge_distance(robot, env: WarehouseEnv) -> int:
    return min(manhattan_distance(robot.position, cs.position)
               for cs in env.charge_stations)


# Validates if a package is worth pursuing based on:
# 1. Enough time steps remaining.
# 2. Enough battery to complete the trip.
# 3. The package is not currently held by the opponent.
def is_package_available(robot, package, opponent, remaining_moves) -> bool:
    cost = get_cost(robot, package)
    return (remaining_moves >= cost and
            robot.battery >= cost and
            opponent.package is not package)


# --------------------------- Heuristic Logic -----------------------------------

# Evaluates the maximum potential value a robot can achieve given the current state.
# Considers both packages on the board and the package currently held (if any).
# Now also returns the cost to the best package (for proximity bonus).
def get_max_package_value(robot, opponent, env: WarehouseEnv) -> tuple:
    max_value = 0
    best_cost = float('inf')
    remaining_moves = (env.num_steps + 1) // 2

    # 1. Check packages currently on the board
    for package in env.packages:
        if package.on_board and is_package_available(robot, package, opponent, remaining_moves):
            cost = get_cost(robot, package)
            # Heuristic score: Reward divided by Cost (Efficiency)
            value = get_reward(package) / cost
            if value > max_value:
                max_value = value
                best_cost = cost
            elif value == max_value:
                best_cost = min(best_cost, cost)

    # 2. Check if robot is already carrying a package
    if robot.package is not None:
        package = robot.package
        cost = get_cost(robot, package)
        if remaining_moves >= cost and robot.battery >= cost and cost > 0:
            value = get_reward(package) / cost
            if value > max_value:
                max_value = value
                best_cost = cost
            elif value == max_value:
                best_cost = min(best_cost, cost)

    return max_value, best_cost


# complex heuristic function combining multiple game factors:
# - Potential package values for self vs opponent.
# - Current score difference (Credit).
# - Battery advantage (relative to nearest charging station).
# - Proximity bonus: rewards being closer to the best available package.
def smart_heuristic(env: WarehouseEnv, robot_id: int):
    robot = env.get_robot(robot_id)
    opponent = env.get_robot((robot_id + 1) % 2)

    # Calculate potential future gains (now also returns cost to best package)
    max_value_me, best_cost_me = get_max_package_value(robot, opponent, env)
    max_value_opp, best_cost_opp = get_max_package_value(opponent, robot, env)

    # Calculate current state advantages
    credit_diff = robot.credit - opponent.credit

    battery_advantage_me = robot.battery - get_min_charge_distance(robot, env)
    battery_advantage_opp = opponent.battery - get_min_charge_distance(opponent, env)

    # Proximity bonus: penalize distance to best package (lower cost = higher score)
    proximity_me = -best_cost_me if best_cost_me < float('inf') else 0
    proximity_opp = -best_cost_opp if best_cost_opp < float('inf') else 0

    carrying_bonus_me = 0
    carrying_bonus_opp = 0
    if robot.package is not None:
        carrying_bonus_me = -manhattan_distance(robot.position, robot.package.destination)
    if opponent.package is not None:
        carrying_bonus_opp = -manhattan_distance(opponent.position, opponent.package.destination)

    # Weighted sum of components
    return (10 * max_value_me
            - 10 * max_value_opp
            + 10 * credit_diff
            + battery_advantage_me
            - battery_advantage_opp
            + 3 * proximity_me
            - 1 * proximity_opp
            + 3 * carrying_bonus_me
            - 1 * carrying_bonus_opp)

smart_heurisitc = smart_heuristic


# ==================================================================================
#                            Class: AgentGreedyImproved
# ==================================================================================

class AgentGreedyImproved(AgentGreedy):
    # Overrides the base heuristic with the smart evaluation function
    def heuristic(self, env: WarehouseEnv, robot_id: int):
        return smart_heuristic(env, robot_id)


# ==================================================================================
#                               Class: AgentMinimax
# ==================================================================================

class AgentMinimax(Agent):
    # Overrides the base heuristic with the smart evaluation function
    def heuristic(self, env: WarehouseEnv, robot_id: int):
        return smart_heuristic(env, robot_id)

    # --------------------------- Main Execution Loop -------------------------------
    # Main entry point: Manages Iterative Deepening and Time Limits
    def run_step(self, env: WarehouseEnv, agent_id, time_limit):
        self.startTime = time.time()
        self.timeLimit = time_limit
        self.agentId = agent_id

        # Explicit initialization
        currentDepth = 1
        operators, _ = self.successors(env, agent_id)

        # Safety: Always have a valid fallback move in case time runs out immediately
        if not operators:
            return "park"
        bestMove = operators[0]

        # Iterative Deepening Loop
        while True:
            if self._isTimeUp():
                break

            # Perform search at current depth
            resultScore, resultMove = self.minimaxSearch(env, agent_id, currentDepth, True)

            # Critical: Check time again. If search was cut short, do not trust the result.
            if self._isTimeUp():
                break

            # Only update bestMove if we completed the full search depth successfully
            bestMove = resultMove
            currentDepth += 1

        return bestMove

    # -------------------------- Search Algorithm -----------------------------------

    # Checks if the allocated time slice has expired (with safety margin)
    def _isTimeUp(self):
        return (time.time() - self.startTime) >= (self.timeLimit - 0.1)

    # Recursive Minimax implementation
    def minimaxSearch(self, env, playerId, depth, isMaximizing):
        # Base cases: Terminal state, depth limit reached, or timeout
        if self._isTimeUp():
            return 0, None

        if depth == 0 or env.done():
            return self.heuristic(env, self.agentId), None

        operators, children = self.successors(env, playerId)

        bestOp = None

        if isMaximizing:
            # --- Maximizing Player (Agent) ---
            bestVal = -float('inf')
            for i in range(len(children)):
                if self._isTimeUp():
                    break
                # Recursively call for opponent (Minimizer)
                val, _ = self.minimaxSearch(children[i], (playerId + 1) % 2, depth - 1, False)

                if val > bestVal:
                    bestVal = val
                    bestOp = operators[i]
            return bestVal, bestOp

        else:
            # --- Minimizing Player (Opponent) ---
            bestVal = float('inf')
            for i in range(len(children)):
                if self._isTimeUp():
                    break
                # Recursively call for agent (Maximizer)
                val, _ = self.minimaxSearch(children[i], (playerId + 1) % 2, depth - 1, True)

                if val < bestVal:
                    bestVal = val
                    bestOp = operators[i]
            return bestVal, bestOp


# ==================================================================================
#                               Class: AgentAlphaBeta
# ==================================================================================

# Custom exception for instant timeout exit
class SearchTimeout(Exception):
    pass

class AgentAlphaBeta(Agent):
    # Overrides the base heuristic with the smart evaluation function
    def heuristic(self, env: WarehouseEnv, robot_id: int):
        return smart_heuristic(env, robot_id)

    # --------------------------- Main Execution Loop -------------------------------
    def run_step(self, env: WarehouseEnv, agent_id, time_limit):
        self.startTime = time.time()
        self.timeLimit = time_limit
        self.agentId = agent_id

        currentDepth = 1
        operators = env.get_legal_operators(agent_id)

        # Safety fallback
        if not operators:
            return "park"
        bestMove = operators[0]

        # Iterative Deepening Loop with exception-based timeout
        try:
            while True:
                self._checkTime()

                # Start search with full Alpha-Beta window (-inf, +inf)
                resultScore, resultMove = self.alphaBetaSearch(env, agent_id, currentDepth, True, -float('inf'),
                                                               float('inf'))

                bestMove = resultMove
                currentDepth += 1

        except SearchTimeout:
            pass  # Time's up - return best move from last completed depth

        return bestMove

    # -------------------------- Search Algorithm -----------------------------------

    def _checkTime(self):
        if (time.time() - self.startTime) >= (self.timeLimit - 0.1):
            raise SearchTimeout()

    # Recursive Alpha-Beta Pruning implementation
    def alphaBetaSearch(self, env, playerId, depth, isMaximizing, curAlpha, curBeta):
        # Time check at every node
        self._checkTime()

        if depth == 0 or env.done():
            return self.heuristic(env, self.agentId), None

        operators = env.get_legal_operators(playerId)

        move_priority = {
            'drop off': 0, 'pick up': 1, 'charge': 2,
            'move south': 3, 'move east': 4, 'move west': 5, 'move north': 6, 'park': 7
        }
        operators.sort(key=lambda op: move_priority.get(op, 8))

        bestOp = None

        if isMaximizing:
            # --- Maximizing Player ---
            bestVal = -float('inf')
            for op in operators:
                # Lazy expansion: clone one child at a time
                child = env.clone()
                child.apply_operator(playerId, op)

                val, _ = self.alphaBetaSearch(child, (playerId + 1) % 2, depth - 1, False, curAlpha, curBeta)

                if val > bestVal:
                    bestVal = val
                    bestOp = op

                # Update Alpha & Prune
                curAlpha = max(curAlpha, bestVal)
                if curAlpha >= curBeta:
                    break  # Beta Cutoff (Pruning)
            return bestVal, bestOp
        else:
            # --- Minimizing Player ---
            bestVal = float('inf')
            for op in operators:
                # Lazy expansion: clone one child at a time
                child = env.clone()
                child.apply_operator(playerId, op)

                val, _ = self.alphaBetaSearch(child, (playerId + 1) % 2, depth - 1, True, curAlpha, curBeta)

                if val < bestVal:
                    bestVal = val
                    bestOp = op

                # Update Beta & Prune
                curBeta = min(curBeta, bestVal)
                if curBeta <= curAlpha:
                    break  # Alpha Cutoff (Pruning)
            return bestVal, bestOp
# ==================================================================================
#                               Class: AgentExpectimax
# ==================================================================================

class AgentExpectimax(Agent):
    # Overrides the base heuristic with the smart evaluation function
    def heuristic(self, env: WarehouseEnv, robot_id: int):
        return smart_heuristic(env, robot_id)

    # --------------------------- Main Execution Loop -------------------------------
    def run_step(self, env: WarehouseEnv, agent_id, time_limit):
        self.startTime = time.time()
        self.timeLimit = time_limit
        self.agentId = agent_id

        currentDepth = 1
        operators, _ = self.successors(env, agent_id)

        # Safety fallback
        if not operators:
            return "park"
        bestMove = operators[0]

        # Iterative Deepening Loop
        while True:
            if self._isTimeUp():
                break

            resultScore, resultMove = self.expectimaxSearch(env, agent_id, currentDepth, True)

            if self._isTimeUp():
                break

            bestMove = resultMove
            currentDepth += 1

        return bestMove

    # -------------------------- Search Algorithm -----------------------------------

    def _isTimeUp(self):
        return (time.time() - self.startTime) >= (self.timeLimit - 0.1)

    # Recursive Expectimax implementation
    def expectimaxSearch(self, env, playerId, depth, isMaximizing):
        # Base cases
        if self._isTimeUp():
            return 0, None

        if depth == 0 or env.done():
            return self.heuristic(env, self.agentId), None

        operators, children = self.successors(env, playerId)
        bestOp = None

        if isMaximizing:
            # --- Max Node ---
            # Standard maximization strategy
            bestVal = -float('inf')
            for i in range(len(children)):
                if self._isTimeUp():
                    break
                val, _ = self.expectimaxSearch(children[i], (playerId + 1) % 2, depth - 1, False)

                if val > bestVal:
                    bestVal = val
                    bestOp = operators[i]
            return bestVal, bestOp

        else:
            # --- Chance Node ---
            # Calculates weighted average based on probability of moves
            totalScore = 0.0
            totalWeight = 0.0

            for i in range(len(children)):
                if self._isTimeUp():
                    break
                val, _ = self.expectimaxSearch(children[i], (playerId + 1) % 2, depth - 1, True)

                # Assign probability weights to specific moves
                # "move west" or "pick up" are considered more likely (weight 3.0)
                op = operators[i]
                weight = 1.0
                if op == "move west" or op == "pick up":
                    weight = 3.0

                totalScore += val * weight
                totalWeight += weight

            # Avoid division by zero
            if totalWeight == 0:
                return 0, None

            # Return Expected Value (Average)
            return (totalScore / totalWeight), None


# ==================================================================================
#                               Class: AgentHardCoded
# ==================================================================================

# here you can check specific paths to get to know the environment
class AgentHardCoded(Agent):
    def __init__(self):
        self.step = 0
        # specifiy the path you want to check - if a move is illegal - the agent will choose a random move
        self.trajectory = ["move north", "move east", "move north", "move north", "pick_up", "move east", "move east",
                           "move south", "move south", "move south", "move south", "drop_off"]

    def run_step(self, env: WarehouseEnv, robot_id, time_limit):
        if self.step == len(self.trajectory):
            return self.run_random_step(env, robot_id, time_limit)
        else:
            op = self.trajectory[self.step]
            if op not in env.get_legal_operators(robot_id):
                op = self.run_random_step(env, robot_id, time_limit)
            self.step += 1
            return op

    def run_random_step(self, env: WarehouseEnv, robot_id, time_limit):
        operators, _ = self.successors(env, robot_id)

        return random.choice(operators)