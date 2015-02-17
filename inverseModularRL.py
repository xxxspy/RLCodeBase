import modularAgents
import featureExtractors

import numpy as np
from scipy.optimize import minimize

import sys
import modularQFuncs

class InverseModularRL:
  """
    Inverse Reinforcement Learning. From a trained modular agent, find the weights given
    - Q tables of modules
    - Policy function

    This is implemented as
    C. A. Rothkopf and Ballard, D. H.(2013), Modular inverse reinforcement
    learning for visuomotor behavior, Biological Cybernetics,
    107(4),477-490
    http://www.cs.utexas.edu/~dana/Biol_Cyber.pdf
  """

  def __init__(self, qFuncs, eta = 5):
    """
      Args:
        qFuncs: a list of Q functions for all the modules
    """
    self.qFuncs = qFuncs

    # confidence
    self.eta = eta

  def setSamplesFromMdp(self, mdp, agent):
    """
    One way to set the samples.
    Read form mdp and get the policies of states.

    Set self.getSamples and self.getActions here.
    """
    states = mdp.getStates()
    self.getSamples = lambda : [(state, agent.getPolicy(state)) for state in states]
    self.getActions = lambda s : mdp.getPossibleActions(s)

  def setSamples(self, samples):
    """
    Read from subj*.parsed.mat file.

    Set self.getSamples and self.getActions here.
    """
    self.getSamples = lambda : samples
    # FIXME overfit
    self.getActions = lambda s : ['L', 'R', 'G']

  def printSamples(self):
    samples = self.getSamples()

    for state, action in samples:
      print state
      print action
    
  def obj(self, X):
    """
      The objective function to be minimized.

      Args:
        X: parameter vector.
      Return:
        the function value
    """
    w = X
    ret = 0

    # replay the process
    for state, optAction in self.getSamples():
      # Update the weights for each module accordingly.
      for moduleIdx in xrange(len(self.qFuncs)):
        # check whether this module is off
        ret += self.eta * w[moduleIdx] * self.qFuncs[moduleIdx](state, optAction)

        # denominator
        denom = 0
        actionSet = self.getActions(state)
        for action in actionSet:
          denom += np.exp(self.eta * w[moduleIdx] * self.qFuncs[moduleIdx](state, action))

        ret -= np.log(denom)

    # This is to be minimized, take the negative.
    return - ret

  def findWeights(self):
    """
      Find the approporiate weight for each module, by walking through the policy.

      Return:
        optimal weight
    """
    n = len(self.qFuncs)
    start_pos = np.zeros(n)
    
    # range of weights
    bnds = tuple((0, 1) for x in start_pos)

    # constraints: sum to be 1
    cons = ({'type': 'eq', 'fun': lambda x:  1 - sum(x)})

    w = minimize(self.obj, start_pos, method='SLSQP', bounds=bnds ,constraints=cons)
    return w

def checkPolicyConsistency(states, a, b):
  """
    Check how many policies on the states are consistent with the optimal one.

    Args:
      states: the set of states that we want to compare the policies
      a, b: two agents that we want to compare their policies
    Return:
      Portion of consistent policies
  """
  consistentPolices = 0

  # Walk through each state
  for state in states:
    consistentPolices += int(a.getPolicy(state) == b.getPolicy(state))

  return 1.0 * consistentPolices / len(states)

def getWeightDistance(w1, w2):
  """
    Return:
      ||w1 - w2||_2
  """
  assert len(w1) == len(w2)

  return np.linalg.norm([w1[i] - w2[i] for i in range(len(w1))])

def continuousWorldExperiment():
  """
    Can be called to run pre-specified agent and domain.
  """
  import continuousWorld as cw
  init = cw.loadFromMat('miniRes25.mat', 0)
  #init = cw.toyDomain()
  m = cw.ContinuousWorld(init)
  env = cw.ContinuousEnvironment(m)

  actionFn = lambda state: m.getPossibleActions(state)
  qLearnOpts = {'gamma': 0.9,
                'alpha': 0.5,
                'epsilon': 0,
                'actionFn': actionFn}
  # modular agent
  a = modularAgents.ModularAgent(**qLearnOpts)

  if len(sys.argv) > 1:
    # user wants to set weights themselves
    w = map(float, sys.argv[1:])
    a.setWeights(w)

  qFuncs = modularQFuncs.getContinuousWorldFuncs(m)
  # set the weights and corresponding q-functions for its sub-mdps
  # note that the modular agent is able to determine the optimal policy based on these
  a.setQFuncs(qFuncs)

  sln = InverseModularRL(qFuncs)
  sln.setSamplesFromMdp(m, a)
  output = sln.findWeights()
  w = output.x.tolist()
  w = map(lambda _: round(_, 5), w) # avoid weird numerical problem

  print "Weight: ", w

  # check the consistency between the original optimal policy
  # and the policy predicted by the weights we guessed.
  aHat = modularAgents.ModularAgent(**qLearnOpts)
  aHat.setQFuncs(qFuncs)
  aHat.setWeights(w) # get the weights in the result

  # print for experiments
  print checkPolicyConsistency(m.getStates(), a, aHat)
  print getWeightDistance(a.getWeights(), w)

  return w, sln

def getSamplesFromMat(filenames, idxSet):
  """
  Get human actions and states from mat files.
  """
  samples = []

  import util

  for filename in filenames:
    mat = util.loadmat(filename)

    for idx in idxSet:
      obstDist = mat['pRes'][idx].obstDist1
      obstAngle = mat['pRes'][idx].obstAngle1 / 180.0 * np.pi
      obstDist2 = mat['pRes'][idx].obstDist2
      obstAngle2 = mat['pRes'][idx].obstAngle2 / 180.0 * np.pi

      targDist = mat['pRes'][idx].targDist1
      targAngle = mat['pRes'][idx].targAngle1 / 180.0 * np.pi
      targDist2 = mat['pRes'][idx].targDist2
      targAngle2 = mat['pRes'][idx].targAngle2 / 180.0 * np.pi

      segDist = mat['pRes'][idx].pathDist
      segAngle = mat['pRes'][idx].pathAngle / 180.0 * np.pi

      actions = mat['pRes'][idx].action

      # cut the head and tail samples
      for i in range(5, len(targDist) - 15):
        state = ((targDist[i], targAngle[i]),
                 (targDist2[i], targAngle2[i]),
                 (obstDist[i], obstAngle[i]),
                 (obstDist2[i], obstAngle2[i]),
                 (segDist[i], segAngle[i]))
        action = actions[i]
        samples.append((state, action))

  return samples

def debugWeight(sln, filename):
  import matplotlib.pyplot as plt

  data = []
  for i in range(0, 11):
    row = []
    for j in range(0, 11 - i):
      k = 10 - i - j
      row.append(-sln.obj([0.1 * i, 0.1 * j, 0.1 * k]))
    for j in range(11 - i, 11):
      row.append(0) # will be masked
    data.append(row)

  mask = np.tri(11, k=-1)
  mask = np.fliplr(mask)
  data = np.ma.array(data, mask=mask)

  plt.imshow(data, interpolation='none')
  plt.xticks(range(11), np.arange(0,1.1,0.1))
  plt.yticks(range(11), np.arange(0,1.1,0.1))
  plt.xlabel('Obstacle Module Weight');
  plt.ylabel('Target Module Weight');

  plt.jet()
  plt.colorbar()

  plt.savefig(filename)

def policyCompare(samples, w):
  """
  Given samples and weights, compare policies of human and our agent.
  Args:
    samples: list of (state, action)
    w: weight learned
  Return:
    Proportion of agreed policies
  """
  # define agent
  import modularAgents
  import humanWorld
  actionFn = lambda state: humanWorld.HumanWorld.actions
  qLearnOpts = {'gamma': 0.9,
                'alpha': 0.5,
                'epsilon': 0,
                'actionFn': actionFn}
  a = modularAgents.ModularAgent(**qLearnOpts)
  a.setWeights(w)
  a.setQFuncs(modularQFuncs.getHumanWorldDiscreteFuncs())

  # go through samples
  agreedPolicies = 0
  for state, action in samples:
    agreedPolicies += a.getPolicy(state) == action 

  return 1.0 * agreedPolicies / len(samples)

def humanWorldExperiment(filenames, rang):
  """
  Args:
    rang: load mat with given rang of trials
  """
  print rang, ": Started."
  #qFuncs = modularAgents.getHumanWorldContinuousFuncs()
  qFuncs = modularQFuncs.getHumanWorldDiscreteFuncs()

  sln = InverseModularRL(qFuncs)
  samples = getSamplesFromMat(filenames, rang)
  sln.setSamples(samples)

  output = sln.findWeights()
  w = output.x.tolist()
  w = map(lambda _: round(_, 5), w) # avoid weird numerical problem
  agreedPoliciesRatio = policyCompare(samples, w)

  print rang, ": weights are", w
  print rang, ": proportion of agreed policies ", agreedPoliciesRatio 
  print rang, ": OK."

  debugWeight(sln, 'objValuesTask' + str(rang[0] / len(rang) + 1) + '.png')
  return [w, agreedPoliciesRatio] 

if __name__ == '__main__':
  # run tasks in parallel (mine is quad-core)
  from multiprocessing import Pool
  pool = Pool(processes=4)

  subjFiles = ["subj" + str(num) + ".parsed.mat" for num in xrange(25, 29)]
  taskRanges = [range(0, 8), range(8, 16), range(16, 24), range(24, 31)]
  #humanWorldExperiment(subjFiles, taskRanges[0])
  results = [pool.apply_async(humanWorldExperiment, args=(subjFiles, ids)) for ids in taskRanges]

  import pickle
  weights = [r.get()[0] for r in results]
  agreedPoliciesRatios = [r.get()[1] for r in results]

  output = open('weights.pkl', 'wb')
  pickle.dump(weights, output)
  output.close()

  output = open('agreedPolicies.pkl', 'wb')
  pickle.dump(agreedPoliciesRatios, output)
  output.close()
