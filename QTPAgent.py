import copy
import util
import pprint
import config
import random
from cmp import QueryType
import numpy
from copy import deepcopy
import scipy.stats
import easyDomains
from valueIterationAgents import ValueIterationAgent
try:
  from lp import computeValue, computeObj, milp, lp, lpDual
except ImportError: print "lp import error"

class LPAgent(ValueIterationAgent):
  def learn(self):
    args = {}
    args['S'] = self.mdp.getStates()
    args['A'] = self.mdp.getPossibleActions(self.mdp.state) # assume state actions are available for all states
    def transition(s, a, sp):
      trans = self.mdp.getTransitionStatesAndProbs(s, a)
      trans = filter(lambda (state, prob): state == sp, trans)
      if len(trans) > 0: return trans[0][1]
      else: return 0
    args['T'] = transition
    args['r'] = self.mdp.getReward
    args['s0'] = self.mdp.state
    self.v = lp(**args)
  
  def getValue(self, state, t=0):
    return self.v[state]

class LPDualAgent(ValueIterationAgent):
  def learn(self):
    args = {}
    args['S'] = self.mdp.getStates()
    args['A'] = self.mdp.getPossibleActions(self.mdp.state) # assume state actions are available for all states
    def transition(s, a, sp):
      trans = self.mdp.getTransitionStatesAndProbs(s, a)
      trans = filter(lambda (state, prob): state == sp, trans)
      if len(trans) > 0: return trans[0][1]
      else: return 0
    args['T'] = transition
    args['r'] = self.mdp.getReward
    args['s0'] = self.mdp.state
    self.opt, self.x = lpDual(**args)
  
  def getValue(self, state, t=0):
    if state == self.mdp.state:
      return self.opt
    else:
      raise Exception("getValue for arbitrary state is undefined " + str(state))

  def getPolicies(self, state, t=0):
    actions = self.mdp.getPossibleActions(state)
    maxProb = max(self.x[state, a] for a in actions)
    return filter(lambda a: self.x[state, a] == maxProb, actions)

#LearningAgent = ValueIterationAgent
#LearningAgent = LPAgent
LearningAgent = LPDualAgent

class QTPAgent:
  def __init__(self, cmp, ws, initialPhi, queryType,
               gamma, clusterDistance=0):
    # underlying cmp
    self.cmp = cmp
    # set of possible reward functions
    self.ws = ws
    # create the reward function representation for each w \in ws
    # FIXME let's assume feature decomposition in general from now on, unless we further change our research direction
    # will make this compatible with other algorithms later 
    self.rewardSet = map(lambda w: self.wToReward(w), ws)
    self.gamma = gamma
    # init belief on rewards in rewardSet
    self.phi = initialPhi
    self.queryType = queryType

    self.clusterDistance = clusterDistance
    self.rewardClusters = util.Counter()
    
    self.preprocess()
    
  def resetPsi(self, psi):
    self.phi = psi
    
    self.cmp.reset()
    self.preprocess()

  def preprocess(self):
    # bookkeep our in-mind planning
    self.responseToPhi = util.Counter()
    self.phiToPolicy = util.Counter()
    horizon = self.cmp.horizon
    terminalReward = self.cmp.terminalReward

    # initialize VI agent for reward set for future use
    self.viAgentSet = util.Counter()
    self.rewardSetSize = len(self.rewardSet)

    if self.queryType in [QueryType.ACTION, QueryType.SIMILAR]:
      # For these queries, we need to compute the optimal policies (also values, occupancies for all reward candidates:
      # action queries: we need the optimal actions for all the states.
      # trajectory queries: we need to compute the occupancies of state action pairs.
      for idx in range(self.rewardSetSize):
        phi = [0] * self.rewardSetSize
        phi[idx] = 1
        
        if horizon == numpy.inf: self.viAgentSet[idx] = self.getVIAgent(phi)
        # double check this for planning with transient phase
        else: self.viAgentSet[idx] = self.getFiniteVIAgent(phi, horizon, terminalReward, posterior=True)
        #print idx, self.viAgentSet[idx].getValue(self.cmp.state)

  def sampleTrajectory(self, pi = None, state = None, hori = numpy.inf, to = 'occupancy'):
    # sample a trajectory by following pi starting from self.state until state that is self.isTerminal
    # pi: S, A -> prob
    u = util.Counter()
    states = []
    actions = []

    t = 0
    if state: self.cmp.state = state

    # we use self.cmp for simulation. we reset it after running
    while True:
      if self.cmp.isTerminal(self.cmp.state) or t >= hori: break

      # now, sample an action following this policy
      if pi == None:
        a = random.choice(self.cmp.getPossibleActions())
      else:
        a = util.sample({a: pi(self.cmp.state, a) for a in self.cmp.getPossibleActions()})
      u[(self.cmp.state, a)] = 1
      states.append(self.cmp.state)
      actions.append(a)
      t += 1

      self.cmp.doAction(a)
    self.cmp.reset()
    
    if to == 'occupancy':
      return u
    elif to == 'trajectory':
      return states
    elif to == 'saPairs':
      return zip(states, actions)
    else:
      raise Exception('unknown return type')

  def sampleTrajFromRewardCandidate(self, idx, state):
    return tuple(self.sampleTrajectory(self.viAgentSet[idx].x, state, hori=config.TRAJECTORY_LENGTH, to='trajectory'))

  def getRewardFunc(self, phi):
    """
    return the mean reward function under the given belief
    """
    if type(phi) == int:
      return self.rewardSet[phi]
    else:
      # now we have the feature-based representation of rewardSet
      return lambda state, action: sum([reward(state, action) * p for reward, p in zip(self.rewardSet, phi)])
  
  def wToReward(self, w):
    """
    convert \omega to a reward function
    
    return: a function of state action pair that returns its reward under reward parameter w
    """
    def wtr(state, action):
      # leave space here for debugging
      return numpy.dot(w, self.cmp.getFeatures(state, action))
    return wtr

  def optimizeW(self, w):
    """
    optimize a reward parameter w
    
    return: the occupancy measure the optimal policy under w
    """
    horizon = self.cmp.horizon
    terminalReward = self.cmp.terminalReward

    rewardFunc = self.wToReward(w)
    cmp = deepcopy(self.cmp)
    cmp.getReward = rewardFunc
    agent = LearningAgent(cmp, discount=self.gamma, iterations=horizon, initValues=terminalReward)
    agent.learn()
    return agent.x

  def getVIAgent(self, phi, posterior=False):
    """
    Return a trained value iteration agent with given phi.
    So we can use getValue, getPolicy, getQValue, etc.
    """
    if posterior and tuple(phi) in self.viAgentSet.keys():
      return self.viAgentSet[tuple(phi)]
    else:
      rewardFunc = self.getRewardFunc(phi)
      cmp = deepcopy(self.cmp)
      cmp.getReward = rewardFunc
      vi = LearningAgent(cmp, discount=self.gamma)
      vi.learn()
      if posterior: self.viAgentSet[tuple(phi)] = vi # bookkeep
      return vi
  
  def getFiniteVIAgent(self, phi, horizon, terminalReward, posterior=True):
    if posterior and tuple(phi) in self.viAgentSet.keys():
      # bookkeep posterior optimal policies
      return self.viAgentSet[tuple(phi)]
    else:
      rewardFunc = self.getRewardFunc(phi)
      cmp = deepcopy(self.cmp)
      cmp.getReward = rewardFunc
      if posterior:
        vi = LearningAgent(cmp, discount=self.gamma, iterations=horizon, initValues=terminalReward)
      else:
        # must use value iteration to derive nonstationary policy for the transient phase
        vi = ValueIterationAgent(cmp, discount=self.gamma, iterations=horizon, initValues=terminalReward)
      vi.learn()
      if posterior: self.viAgentSet[tuple(phi)] = vi # bookkeep
      return vi
 
  def getValue(self, state, phi, policy, horizon):
    """
    Accumulated rewards by following a fixed policy to a time horizon.
    No learning here. 
    """
    v = 0
    rewardFunc = self.getRewardFunc(phi)
    
    for t in range(horizon):
      possibleStatesAndProbs = getMultipleTransitionDistr(self.cmp, state, policy, t)
      v += self.gamma ** t * sum([rewardFunc(s) * prob for s, prob in possibleStatesAndProbs])
    
    return v

  def getConsistentCond(self, query):
    actions = self.cmp.getPossibleActions(query)
    responseTime = self.cmp.getResponseTime()
    # belief -> prob dict

    if self.queryType == QueryType.ACTION:
      resSet = actions
      consistCond = lambda res, idx: res in self.viAgentSet[idx].getPolicies(query, responseTime)
    elif self.queryType in [QueryType.POLICY, QueryType.DEMONSTRATION]:
      # query is a set of policies or trajectories
      # note that for trajectories, the occupancies are either 1 or 0 for any state action pair
      resSet = query
      # consistent if the true reward has the largest value on this policy
      def consistCond(res, idx):
        piValues = {piIdx: self.computeV(query[piIdx],\
                                        self.cmp.getStates(),\
                                        self.cmp.getPossibleActions(),\
                                        self.getRewardFunc(idx),\
                                        self.cmp.horizon\
                                        )
                    for piIdx in range(len(query))}
        maxValue = max(piValues.values())
        optPiIdxs = filter(lambda piIdx: piValues[piIdx] == maxValue, range(len(query)))
        return any(res == query[piIdx] for piIdx in optPiIdxs)
    elif self.queryType == QueryType.PARTIAL_POLICY:
      resSet = query
      # consistent if the true reward has the largest value on this policy
      def consistCond(res, idx):
        piValues = {}
        for piIdx in range(len(query)):
          obj, _ = lpDual(self.args['S'], self.args['A'], self.args['R'][idx], self.args['T'], self.args['s0'], query[piIdx])
          piValues[piIdx] = obj
        maxValue = max(piValues.values())
        optPiIdxs = filter(lambda piIdx: piValues[piIdx] == maxValue, range(len(query)))
        return any(res == query[piIdx] for piIdx in optPiIdxs)
    elif self.queryType == QueryType.REWARD_SIGN:
      resSet = [-1, 0, 1]
      consistCond = lambda res, idx: numpy.sign(self.rewardSet[idx](query)) == res
    elif self.queryType == QueryType.REWARD:
      resSet = self.cmp.possibleRewardValues
      consistCond = lambda res, idx: self.rewardSet[idx](query) == res
    elif self.queryType == QueryType.SIMILAR:
      resSet = query
      consistDict = {}
      for idx in xrange(self.rewardSetSize):
        x = self.viAgentSet[idx].x
        optTrajs = [self.sampleTrajectory(x, query[0][0], hori=config.TRAJECTORY_LENGTH, to='trajectory') for _ in range(5)]
        resDists = {res: sum(self.cmp.getTrajectoryDistance(res, optTraj) for optTraj in optTrajs) for res in resSet}
        for res in resSet:
          # check if the distance from res to x[idx] is smaller than all other reward candidates
          consistDict[res, idx] = all(resDists[res] <= resDists[otherRes] for otherRes in resSet)
      consistCond = lambda res, idx: consistDict[res, idx]
    elif self.queryType == QueryType.COMMITMENT:
      #FIXME only for l = 1

      # the operator returns the commitment directly
      resSet = query
      # the consistent condition is that, under such commitment, the operator can get higher value
      # than other commitments provided
      def consistCond(res, idx):
        maxV = None
        optCommit = None
        for commit in query:
          # compute the operator's value by following this commitment
          value, _ = lpDual(self.args['S'], self.args['A'], self.args['R'][idx], self.args['T'], self.args['s0'], commit)
          if value > maxV:
            maxV = value
            optCommit = commit
        return optCommit == res
    elif self.queryType == QueryType.NONE:
      resSet = [0]
      consistCond = lambda res, idx: True
    else:
      raise Exception('unknown type of query ' + self.queryType)
  
    return resSet, consistCond

  def getPossiblePhiAndProbs(self, query):
    distr = util.Counter()
    resSet, consistCond = self.getConsistentCond(query)

    candAllocated = [False] * self.rewardSetSize
    # consider all possible responses, find out their probabilities,
    # and compute the probability of observing the next phi
    for res in resSet:
      # the probability of observing this res
      resProb = 0
      phi = self.phi[:]
      for idx in range(self.rewardSetSize):
        if (consistCond(res, idx) or res == resSet[-1]) and not candAllocated[idx]:
          # either it is consistent, or it's the last response
          resProb += phi[idx]
          candAllocated[idx] = True
        else:
          phi[idx] = 0
      
      # normalize phi, only record possible phis
      if sum(phi) != 0:
        phi = [x / sum(phi) for x in phi]
        distr[tuple(phi)] += resProb
        #FIXME have trouble to hash policies
        # this will only be used in simulation, called by `respond' method
        #self.responseToPhi[(tuple(query), res)] = tuple(phi)

    # should be true if implemented correctly
    assert all(candAllocated)
    l = map(lambda l: (l[0], l[1]/sum(distr.values())), distr.items())
    return l

  def getQValue(self, state, policy, query):
    """
    Compute the expected return given initial state, transient policy, and a query
    """
    cost = self.cmp.cost(query)

    responseTime = self.cmp.getResponseTime()
    horizon = self.cmp.horizon
    terminalReward = self.cmp.terminalReward
    if responseTime == 0: vBeforeResponse = 0
    else: vBeforeResponse = self.getValue(state, self.phi, policy, responseTime)
    
    possiblePhis = self.getPossiblePhiAndProbs(query)
    possibleStatesAndProbs = getMultipleTransitionDistr(self.cmp, state, policy, responseTime)
    
    vAfterResponse = 0
    for fPhi, fPhiProb in possiblePhis:
      if horizon == numpy.inf: viAgent = self.getVIAgent(fPhi)
      else: viAgent = self.getFiniteVIAgent(fPhi, horizon - responseTime, terminalReward, posterior=True)
      values = lambda state: viAgent.getValue(state)
      estimatedValue = 0
      for fState, fStateProb in possibleStatesAndProbs:
        estimatedValue += values(fState) * fStateProb
      #print fPhi, fPhiProb, estimatedValue
      vAfterResponse += fPhiProb * estimatedValue

    return cost + vBeforeResponse + self.gamma ** responseTime * vAfterResponse
  
  def optimizePolicy(self, query):
    """
    Uses dynamic programming
    """
    v = util.Counter()
    possiblePhis = self.getPossiblePhiAndProbs(query)
    responseTime = self.cmp.getResponseTime()
    horizon = self.cmp.horizon
    terminalReward = self.cmp.terminalReward

    for fPhi, fPhiProb in possiblePhis:
      if horizon == numpy.inf: fViAgent = self.getVIAgent(fPhi)
      else: fViAgent = self.getFiniteVIAgent(fPhi, horizon - responseTime, terminalReward, posterior=True)
      for state in self.cmp.getStates():
        v[state] += fViAgent.getValue(state) * fPhiProb
      
      if horizon == numpy.inf: self.phiToPolicy[tuple(fPhi)] = lambda s, t, agent=fViAgent: agent.getPolicy(s)
      else: self.phiToPolicy[tuple(fPhi)] = lambda s, t, agent=fViAgent: agent.getPolicy(s, t - responseTime)

    # `responseTime` time steps
    viAgent = self.getFiniteVIAgent(self.phi, responseTime, v, posterior=False)
    # this is a non-stationary policy
    pi = lambda s, t: viAgent.getPolicy(s, t)
    
    if config.DEBUG:
      print query, "v func"
      pprint.pprint([(s, viAgent.getValue(s), viAgent.getPolicies(s)) for s in cmp.getStates()])
      
    return pi, viAgent.getValue(self.cmp.state, 0)

  def optimizeQuery(self, state, policy):
    """
    Enumerate relevant considering the states reachable by the transient policy.
    """
    responseTime = self.cmp.getResponseTime()
    horizon = self.cmp.horizon
    possibleRewardLocs = self.cmp.possibleRewardLocations
    possibleStatesAndProbs = getMultipleTransitionDistr(self.cmp, state, policy, responseTime)
    # FIXME
    # assuming deterministic
    fState = possibleStatesAndProbs[0][0]

    # FIXME
    # overfit finite horizon for simplicity
    reachableSet = filter(lambda loc: self.cmp.measure(loc, fState) < horizon - responseTime, possibleRewardLocs)
    
    queries = []
    if self.relevance == None:
      rewardFunc = self.getRewardFunc(self.phi)
      rewardVec = [rewardFunc(loc) for loc in reachableSet]

      # use the default method for query filtering
      for query in self.cmp.queries:
        possiblePhis = self.getPossiblePhiAndProbs(query)
        infGain = False
        for fPhi, fPhiProb in possiblePhis:
          rewardFunc = self.getRewardFunc(fPhi)
          postRewardVec = [rewardFunc(loc) for loc in reachableSet]
          if any(abs(v) > 1e-3 for v in postRewardVec) and scipy.stats.entropy(rewardVec, postRewardVec) > 1e-3:
            infGain = True
            break
        if infGain: queries.append(query)
    elif self.relevance == 'ipp':
      # FIXME OVERFIT
      reachableSet = filter(lambda loc: self.cmp.measure(loc, fState) + self.cmp.measure(loc, (self.cmp.width / 2, self.cmp.height / 2))\
                                        <= horizon - responseTime, possibleRewardLocs)
      rewardFunc = self.getRewardFunc(self.phi)
      rewardVec = [rewardFunc(loc) for loc in reachableSet]

      # use the default method for query filtering
      for query in self.cmp.queries:
        possiblePhis = self.getPossiblePhiAndProbs(query)
        infGain = False
        for fPhi, fPhiProb in possiblePhis:
          rewardFunc = self.getRewardFunc(fPhi)
          postRewardVec = [rewardFunc(loc) for loc in reachableSet]
          if any(abs(v) > 1e-3 for v in postRewardVec) and rewardVec.index(max(rewardVec)) != postRewardVec.index(max(postRewardVec)):
            infGain = True
            break
        if infGain: queries.append(query)
    else:
      # relevance must be a function
      for query in self.cmp.queries:
        if self.relevance(fState, query): queries.append(query)
    
    if config.VERBOSE:
      print "Considering queries", queries

    if config.PRINT == 'queries': print len(queries)

    if queries == []:
      # FIXME pick first query when no relevant queries
      return self.cmp.queries[-1]
    else:
      return max(queries, key=lambda q: self.getQValue(state, policy, q))
 
  def respond(self, query, response):
    """
    The response is informed to the agent regarding a previous query
    """
    # such response was imagined by the agent before and the solution is bookkept
    assert self.responseToPhi[(tuple(query), response)] != 0
    assert self.phiToPolicy[self.responseToPhi[(tuple(query), response)]] != 0
    pi = self.phiToPolicy[self.responseToPhi[(tuple(query), response)]]
    return pi


class JointQTPAgent(QTPAgent):
  def learn(self):
    qList = []
    
    for q in self.cmp.queries:
      # FIXME forget about transient phase
      #pi, qValue = self.optimizePolicy(q)
      qValue = self.getQValue(self.cmp.state, None, q)

      if config.PRINT == 'qs': print qValue
      if config.VERBOSE: print qValue
      qList.append((q, None, qValue))
    
    maxQValue = max(map(lambda _:_[2], qList))
    qList = filter(lambda _: _[2] == maxQValue, qList)

    return random.choice(qList)


class OptimalPolicyQueryAgent(QTPAgent):
  """
  A brute force algorithm that checks all possible partitions of reward candidates.
  Don't worry about its computation time :)
  """
  def learn(self):
    args = easyDomains.convert(self.cmp, self.rewardSet, self.phi)
    k = config.NUMBER_OF_RESPONSES
    responseTime = self.cmp.getResponseTime()
    horizon = self.cmp.horizon
    terminalReward = self.cmp.terminalReward
    from itertools import combinations

    rewardCandNum = len(self.rewardSet)
    maxObjValue = -numpy.inf
    optQ = None
    optPsis = None
    
    values = util.Counter()
    for i in xrange(1, rewardCandNum + 1):
      for l in combinations(range(rewardCandNum), i):
        l = [self.phi[i] if i in l else 0 for i in range(rewardCandNum)]
        if config.VERBOSE: print l
        agent = self.getFiniteVIAgent(l, horizon - responseTime, terminalReward, posterior=True)
        values[tuple(l)] = agent.getValue(self.cmp.state)
    
    for subset in combinations(values.items(), k):
      psis = map(lambda _: _[0], subset)
      qs = map(lambda _: _[1], subset)
      # make sure that such query partitions the reward candiates
      if sum(sum(_ > 0 for _ in psi) for psi in psis) == rewardCandNum and\
         all(sum(psi[i] for psi in psis) > 0 for i in xrange(rewardCandNum)):
        objValue = sum(qs)
        if objValue > maxObjValue:
          maxObjValue = objValue
          optQ = qs
          optPsis = psis
    
    q = None
    if self.queryType == QueryType.POLICY:
      return q, maxObjValue
    elif self.queryType == QueryType.ACTION:
      hList = []
      
      # FIXME has a problem here!
      policyBins = self.computeDominatingPis(args, q)

      for s in args['S']:
        hValue = 0
        for a in args['A']:
          resProb = 0
          bins = [0] * len(q)
          for idx in xrange(rewardCandNum):
            if a in self.viAgentSet[idx].getPolicies(s):
              # increase the probability of observing this 
              resProb += self.phi[idx]
              # put opt policies into bins
              bins = [sum(_) for _ in zip(bins, policyBins[idx])]

          hValue += resProb * scipy.stats.entropy(bins)

        hList.append((s, hValue))

      # sort them nondecreasingly
      hList = filter(lambda _: not scipy.isnan(_[1]), hList)
      hList = sorted(hList, key=lambda _: _[1])
      hList = hList[:1]
    else:
      raise Exception('Query type not implemented for MILP.')

    qList = []
    for q, h in hList:
      # FIXME ignored transient phase
      qValue = self.getQValue(self.cmp.state, None, q)
      qList.append((q, None, qValue))

    maxQValue = max(map(lambda _:_[2], qList))
    qList = filter(lambda _: _[2] == maxQValue, qList)

    return random.choice(qList)


class AprilAgent(QTPAgent):
  """
  Randomly partition psi and find their optimal policies
  Repeat this for finite number of times, specified by ?
  
  only works for k == 2
  """
  def learn(self):
    args = easyDomains.convert(self.cmp, self.rewardSet, self.phi)
    rewardCandNum = len(args['R'])
    k = config.NUMBER_OF_RESPONSES
    assert k == 2 # not going to work for k > 2

    maxV = -numpy.inf
    maxQ = None
    for iterIdx in range(config.SAMPLE_TIMES):
      selector = [random.random() > .5 for _ in xrange(rewardCandNum)]
      # got two psis
      psi0 = [self.phi[_] if selector[_] else 0 for _ in xrange(rewardCandNum)]
      psi1 = [self.phi[_] if not selector[_] else 0 for _ in xrange(rewardCandNum)]
      agent0 = self.getFiniteVIAgent(psi0, self.cmp.horizon - self.cmp.getResponseTime(), self.cmp.terminalReward, posterior=True)
      agent1 = self.getFiniteVIAgent(psi1, self.cmp.horizon - self.cmp.getResponseTime(), self.cmp.terminalReward, posterior=True)
      
      v = agent0.getValue(self.cmp.state) + agent1.getValue(self.cmp.state) 
      if v > maxV:
        maxV = v
        maxQ = [agent0.x, agent1.x]

    return maxQ, None


class AlternatingQTPAgent(QTPAgent):
  def __init__(self, cmp, rewardSet, initialPhi, queryType, gamma, relevance = None, restarts = 0):
    QTPAgent.__init__(self, cmp, rewardSet, initialPhi, queryType, gamma)
    self.relevance = relevance
    self.restarts = restarts

  def learnInstance(self):
    # there could be multiple initializations for AQTP
    # this is learning with one initial query
    state = self.cmp.state
    # learning with queries
    q = random.choice(self.cmp.queries) # initialize with a query
    if config.VERBOSE: print "init q", q
    
    # iterate optimize over policy and query
    counter = 0
    while True:
      prevQ = copy.deepcopy(q)

      pi, qValue = self.optimizePolicy(q)
      q  = self.optimizeQuery(state, pi)
      if config.VERBOSE:
        print "Iteration #", counter
        print "optimized q ", q
      
      if q == prevQ:
        # converged
        break
      counter += 1
    
    return q, pi, qValue
  
  def learn(self):
    results = []
    for _ in xrange(self.restarts + 1):
      results.append(self.learnInstance())
    
    # return the results with maximum q value
    return max(results, key=lambda x: x[2])


class RandomQueryAgent(QTPAgent):
  def learn(self):
    q = random.choice(self.cmp.queries)
    # FIXME ignore transient phase
    qValue = self.getQValue(self.cmp.state, None, q)
    return q, None, qValue


class PriorTPAgent(QTPAgent):
  def __init__(self, cmp, rewardSet, initialPhi, queryType, gamma, relevance = None):
    QTPAgent.__init__(self, cmp, rewardSet, initialPhi, queryType, gamma)
    self.relevance = relevance
  
  def learn(self):
    # mean reward planner
    horizon = self.cmp.horizon
    responseTime = self.cmp.getResponseTime()
    if horizon == numpy.inf:
      meanViAgent = self.getVIAgent(self.phi)
    else:
      terminalReward = self.cmp.terminalReward
      meanViAgent = self.getFiniteVIAgent(self.phi, horizon, terminalReward, posterior=True)
    
    # respond with best query
    state = self.cmp.state
    pi = lambda s, t: meanViAgent.getPolicy(s, t)
    q  = self.optimizeQuery(state, pi)
    qValue = self.getQValue(state, pi, q)

    # update phi to policy 
    possiblePhis = self.getPossiblePhiAndProbs(q)
    for fPhi, fPhiProb in possiblePhis:
      if horizon == numpy.inf: fViAgent = self.getVIAgent(fPhi)
      else: fViAgent = self.getFiniteVIAgent(fPhi, horizon - responseTime, terminalReward, posterior=True)
      
      if horizon == numpy.inf: self.phiToPolicy[tuple(fPhi)] = lambda s, t, agent=fViAgent: agent.getPolicy(s)
      else: self.phiToPolicy[tuple(fPhi)] = lambda s, t, agent=fViAgent: agent.getPolicy(s, t - responseTime)

    return q, pi, qValue


def getMultipleTransitionDistr(cmp, state, policy, time):
  """
  Multiply a transition matrix multiple times.
  Return state -> prob
  """
  p = {s: 0 for s in cmp.getStates()}
  p[state] = 1.0
  
  for t in range(time):
    pNext = {s: 0 for s in cmp.getStates()}
    for s in cmp.getStates():
      if p[s] > 0:
        for nextS, nextProb in cmp.getTransitionStatesAndProbs(s, policy(s, t)):
          pNext[nextS] += p[s] * nextProb
    p = pNext.copy()
  
  assert sum(p.values()) > .99
  return filter(lambda (x, y): y>0, p.items())
