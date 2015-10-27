from QTPAgent import IterativeQTPAgent, JointQTPAgent
from CMPExp import Experiment
import util
from sightseeing import Sightseeing
import random
import sys
import config

scale = 2
width = 10 * scale
height = 10 * scale

# discount factor
gamma = 0.9
# the time step that the agent receives the response
responseTime = 10 * scale

random.seed(sys.argv[1])
queries = [(int((width - 1) * random.random()), int((width - 1) * random.random()), 0)\
           for _ in xrange(10 * scale)]

def main():
  rewards = []
  rewardNum = 5

  for _ in xrange(rewardNum):
    # for each reward candidate, 5 possible sights
    reward = util.Counter()
    for idx in xrange(5 * scale):
      query = random.choice(queries)
      x, y, status = query
      reward[(x, y)] = 1
    rewards.append(reward)

  rewardSet = [rewardGen(reward) for reward in rewards]
  initialPhi = [1.0 / rewardNum] * rewardNum

  #Agent = JointQTPAgent
  Agent = IterativeQTPAgent
  cmp = Sightseeing(queries, rewardSet[0], gamma, responseTime, width, height)
  agent = Agent(cmp, rewardSet, initialPhi, gamma=gamma)
 
  ret, qValue, timeElapsed = Experiment(cmp, agent, gamma, rewardSet, horizon=20)
  print ret
  print qValue

  if config.SAVE_TO_FILE:
    rFile = open('results', 'a')
    rFile.write(str(ret) + '\n')
    rFile.close()

    bFile = open('beliefs', 'a')
    bFile.write(str(qValue) + '\n')
    bFile.close()

    tFile = open('time', 'a')
    tFile.write(str(timeElapsed) + '\n')
    tFile.close()

def rewardGen(rewards): 
  def rewardFunc(s):
    x, y, status = s
    if status == 1:
      if (x, y) in rewards.keys():
        return rewards[(x, y)]
      else:
        return -1
    elif s[0] == width - 1 and s[1] == height - 1:
      return 2
    else:
      return 0
  return rewardFunc

if __name__ == '__main__':
  main()
