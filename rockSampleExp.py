from QTPAgent import AlternatingQTPAgent, JointQTPAgent, RandomQueryAgent
from CMPExp import Experiment
import util
import sys
from rockSample import RockSample
import random
import getopt
import config
from cmp import QueryType
from machineConfigExp import queryIgnored

"""
Algorithms:
- E-JQTP
- AQTP
- AQTP-NF
- AQTP-RS (?)
- opt query
- random query
- no query

Setting:
- response time (axis)

Show:
- expectation Q
- computation time
- paired difference between JQTP and AQTP

TODO:
make this class more general, not just for rocksample exp
"""
def main():
  width = 20
  height = 20
  # the time step that the agent receives the response
  responseTime = 10
  horizon = 40
  # discount factor
  gamma = 0.9
  stepCost = 0
  rewardCandNum = 4
  agentName = 'JQTP'
  
  try:
    opts, args = getopt.getopt(sys.argv[1:], "r:l:s:d:a:c:v")
  except getopt.GetoptError:
    sys.exit(2)
  for opt, arg in opts:
    if opt == '-r':
      random.seed(int(arg))
    elif opt == '-l':
      responseTime = int(arg)
    elif opt == '-s':
      width = height = int(arg)
      horizon = width + height
    elif opt == '-d':
      gamma = float(arg)
    elif opt == '-a':
      agentName = arg
    elif opt == '-c':
      stepCost = float(arg)
    elif opt == '-v':
      config.VERBOSE = True
  
  # sanity check
  assert horizon > responseTime

  queries = [(0, height - 1), (width / 2, height - 1), (width - 1, height - 1),\
             (0, 0), (width / 2, 0), (width - 1, 0)]

  rewards = []
  for _ in xrange(rewardCandNum):
    reward = util.Counter()
    rocks = queries[:]
    # choose bonus rocks
    q = random.choice(rocks)
    reward[q] = 1
    rocks.remove(q)
    # choose other rewards
    for idx in xrange(3):
      q = random.choice(rocks)
      reward[q] = 0.1
      rocks.remove(q)
    rewards.append(reward)
    
  def rewardGen(rewards): 
    def rewardFunc(s):
      if s in rewards.keys():
        return rewards[s]
      else:
        return stepCost
    return rewardFunc
  terminalReward = util.Counter()
  terminalReward[(width / 2, height / 2)] = 100

  def relevance(fState, query):
    return abs(fState[0] - query[0]) + abs(fState[1] - query[1])\
         + abs(query[0] - width / 2) + abs(query[1] - height / 2) < horizon - responseTime

  rewardSet = [rewardGen(reward) for reward in rewards]
  initialPhi = [1.0 / rewardCandNum] * rewardCandNum
  # ask whether reward is good or not
  if agentName == 'NQ':
    queries = [0] # make a dummy query set
    queryType = QueryType.NONE
  else:
    queryType = QueryType.REWARD

  # the true reward function is chosen randomly
  cmp = RockSample(queries, random.choice(rewardSet), gamma, responseTime, width, height,\
                   horizon = horizon, terminalReward = terminalReward)
  cmp.setPossibleRewardValues([0, 0.1, 1])
  if agentName == 'JQTP' or agentName == 'NQ':
    agent = JointQTPAgent(cmp, rewardSet, initialPhi, queryType, gamma)
  elif agentName == 'AQTP':
    agent = AlternatingQTPAgent(cmp, rewardSet, initialPhi, queryType, relevance, gamma)
  elif agentName == 'AQTP-NF':
    # don't filter query. Assume all queries are relevant.
    agent = AlternatingQTPAgent(cmp, rewardSet, initialPhi, queryType, lambda fS, q: True, gamma)
  elif agentName == 'AQTP-RS':
    agent = AlternatingQTPAgent(cmp, rewardSet, initialPhi, queryType, relevance, gamma, restarts=1)
  elif agentName == 'RQ':
    agent = RandomQueryAgent(cmp, rewardSet, initialPhi, queryType, gamma)
  elif agentName == 'TPNQ':
    agent = JointQTPAgent(cmp, rewardSet, initialPhi, queryType, gamma, queryIgnored=True)
  else:
    raise Exception("Unknown Agent " + agentName)

  ret, qValue, time = Experiment(cmp, agent, gamma, rewardSet, queryType, horizon=horizon)
  print ret
  print qValue
  print time

if __name__ == '__main__':
  main()
