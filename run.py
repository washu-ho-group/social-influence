from __future__ import division
from copy import deepcopy
from itertools import repeat
from optparse import OptionParser
import random
import matplotlib.pyplot as plt
import multiprocessing as mp
import numpy as np
import scipy.stats as stats
import time

from item import Item
from user import User
from plat2d import Platform

parser = OptionParser()
parser.add_option("-t", type="float", default=1.0, dest="tau")
parser.add_option("-c", type="float", default=0.5, dest="c")
options = parser.parse_args()[0]
tau, coeff = options.tau, options.c

rdm_quality = False             # assign item quality randomly
calcPerf = [True, False, False] # calculate performance (happiness,distance,topK)
plotQuality = False             # plot item quality
plotHistory = False             # plot rating history
fig_idx = 0
num_free = 1                    # number of free views upon initialization
num_runs = 10                   # number of realizations
num_item = 50                   # total number of items
num_user = 100000               # total number of users (time)
lower, upper = 0, 1             # lower and upper bound of item quality
mu, sigma = 0.5, 0.3            # mean and standard deviation of item quality
ability_range = range(1, 6)     # ability of 1~5
K = 10                          # number of items for "top K in expected top K"
rankModes = ['random', 'quality', 'upvotes', 'ucb', 'lcb']
viewModes = ['first', 'position']
viewMode = viewModes[1]         # how platform displays items to users
n_showed = 1                    # number of items displayed by the platform
p_pos = .5                      # ratio of positional preference in user's choice
                                # p_pos=1 has only positional prefernece
user_c = 0.5                    # coeff of user's lcb
tau = 1                         # power of positional prefernece
coeff = 0.5                     # coeff of platform's ucb/lcb


#********** Initilization
def initialize(seed):

    random.seed(seed)
    np.random.seed(seed)
    items = {}
    users = {}

    #***** Initialization of items
    if not rdm_quality:  # assume item qualities follow a normal distribution between 0~1
        a, b = (lower - mu) / sigma, (upper - mu) / sigma
        qualities = stats.truncnorm(
            a, b, loc=mu, scale=sigma).rvs(size=num_item)
        if plotQuality:
            fig_idx += 1
            plt.figure(fig_idx)
            plt.hist(qualities, normed=True)
            plt.title("Distribution of Item Quality")
            plt.show()

    user0 = User(0, ability_range[-1])
    # assign qualities to items
    for i in range(num_item):
        if rdm_quality:
            q = random.uniform(lower, upper)
        else:
            q = qualities[i]
        items[i] = Item(i, q)
        # each item get free views
        for k in range(num_free):
            items[i].views += 1
            initialEval = user0.evaluate(items[i], method='upvote_only')
            if initialEval:
                items[i].setVotes(initialEval)

    #***** Initialization of users
    for i in range(num_user):
        a = random.choice(ability_range)
        users[i] = User(i, a)

    return items, users


#********** Simulation
def simulate(inputs):
    # np.random.seed(123)
    items, users, rankMode = inputs
    platform = Platform(items=deepcopy(items), users=users)
    perfmeas = platform.run(
        rankMode=rankMode,
        viewMode=viewMode,
        evalMethod="majority",
        perf=calcPerf,
        perfmeasK=K,
        numFree=num_free,
        n_showed=n_showed,
        p_pos=p_pos,
        user_c=user_c,
        tau=tau,
        c=coeff)
    return perfmeas, platform.true_happiness


#********** Start
pool = mp.Pool()
t0 = time.time()
print("-----Start\nnum_runs: {}\nnum_item: {}\nnum_user: {}".format(
    num_runs, num_item, num_user))

# Initialize
seeds = range(num_runs)
inits = pool.map(initialize, seeds)
items, users = zip(*inits)
for i in range(len(seeds)):
    qualities = [itm.getQuality() for itm in items[i].values()]
    mean_quality = np.mean(qualities)
    # print("Seed: {:2}   mean: {}".format(seeds[i], mean_quality))

t_ini = time.time()
print("-----Initialization takes {:.4f}s".format(t_ini - t0))

# Simulate
results = []
for i in range(len(rankModes)):
    result = pool.map_async(simulate, zip(items, users, repeat(rankModes[i])))
    results.append(result)

#perfmeas = list(map(lambda x: x.get(), results))
results = list(map(lambda x: x.get(), results))
perfmeas, true_happiness = zip(* [tuple(zip(*r)) for r in results])

t_done = time.time()
print("-----Simulation takes {:.4f}s".format(t_done - t_ini))

#itms = [
#        list(map(lambda x: [pf['items'] for pf in x], p)) for p in perfmeas
#    ]

#**********  Performance Measurements
true_happiness = np.mean(np.array(true_happiness), axis=1)

if calcPerf[0]:
    happy = [
        list(map(lambda x: [pf['happy'] for pf in x], p)) for p in perfmeas
    ]
    happy = np.mean(np.array(happy), axis=1)
    for i in range(len(rankModes)):
        print("Mode: {:8} happiness: {:.6f}  true: {:.6f}".format(
            rankModes[i], happy[i][-1], true_happiness[i][-1]))

if calcPerf[1]:
    ktd = [list(map(lambda x: [pf['ktd'] for pf in x], p)) for p in perfmeas]
    ktd = np.mean(np.array(ktd), axis=1)
    for i in range(len(rankModes)):
        print("Mode: {:10} distance: {:}".format(rankModes[i], ktd[i][-1]))

if calcPerf[2]:
    topK = [list(map(lambda x: [pf['topK'] for pf in x], p)) for p in perfmeas]
    topK = np.mean(np.array(topK), axis=1)
    for i in range(len(rankModes)):
        print(
            "Mode: {:10} top K percent: {}".format(rankModes[i], topK[i][-1]))

# time to converge
# std_perf = happy[1, :]  #quality
# diff = np.abs([t - s for s, t in zip(std_perf, std_perf[1:])])
# num_consec = 50
# diff = diff < 1e-5
# conv = np.array([sum(diff[i:i + num_consec])
#                  for i, di in enumerate(diff)]) == num_consec
# conv_idx = np.where(conv)[0][0]
# conv_val = std_perf[conv_idx]

# tol = 0.005
# print("Convergenence")
# for i_rm, rm in enumerate(rankModes[2:]):
#     diff_conv = np.abs(happy[i_rm + 2, :] - conv_val) < tol
#     cont_conv = np.array(
#         [sum(diff_conv[i:i + 10]) for i, di in enumerate(diff_conv)]) == 10
#     if sum(cont_conv) > 0:
#         conv_time = np.where(cont_conv)[0][0]
#     else:
#         conv_time = float("inf")
#     print(rm, 'converge time: ', conv_time)

#********** Plotting
if calcPerf[0]:  # user happiness
    fig_idx += 1
    plt.figure(fig_idx)
    for i in range(len(rankModes)):
        plt.plot(happy[i], label='rank by %s' % (rankModes[i]))
        plt.plot(true_happiness[i], label='true_hp %s' % (rankModes[i]))
    plt.title(
        'user happiness VS. time (tau={}, uc={}, lc={}, nshow={}/{}, p_pos={})'.
        format(tau, coeff, user_c, int(n_showed * num_item), num_item, p_pos))
    plt.minorticks_on()
    plt.xlabel('time')
    plt.ylabel('user happiness')
    y_ub = np.ceil(np.max(true_happiness) * 10) / 10
    y_lb = np.floor(np.min(happy) * 10) / 10
    plt.ylim([y_lb, y_ub])
    plt.legend(loc=4)
    plt.grid()
    plt.show()

if calcPerf[1]:  # distance
    fig_idx += 1
    plt.figure(fig_idx)
    for i in range(len(rankModes)):
        plt.plot(ktd[i], label='rank by %s' % (rankModes[i]))
    plt.title('kendall tau distance VS. time (c={})'.format(coeff))
    plt.minorticks_on()
    plt.xlabel('time')
    plt.ylabel('kendall tau distance')
    y_lb = np.min(ktd)
    y_lb = np.floor(y_lb * 10) / 10
    plt.ylim([y_lb, 1])
    plt.legend()
    plt.grid()
    plt.show()

if calcPerf[2]:  # top K
    fig_idx += 1
    plt.figure(fig_idx)
    for i in range(len(rankModes)):
        plt.plot(topK[i], label='rank by %s' % (rankModes[i]))
    plt.title("top {} percentage VS. time (c={})".format(K, coeff))
    plt.minorticks_on()
    plt.xlabel('time')
    plt.ylabel("top {} percentage".format(K))
    y_lb = np.min(topK)
    y_lb = np.floor(y_lb * 10) / 10
    plt.ylim([y_lb, 1])
    plt.legend()
    plt.grid()
    plt.show()

if plotHistory:
    fig_idx += 1
    plt.figure(fig_idx)
    plt.imshow(evalHistory, cmap=plt.cm.Blues, interpolation='nearest')
    plt.title('Individual Evaluation History')
    plt.minorticks_on()
    plt.xlabel('user')
    plt.ylabel('item')
    plt.tick_params(labelright='on')
    plt.yticks(
        range(0, num_item), [
            str(i) + "(" + str(int(itm.getQuality() * 100) / 100) + ")"
            for i, itm in enumerate(platform.items.values())
        ],
        fontsize=6)
    plt.colorbar(orientation='horizontal')
    plt.show()

# t_plt = time.time()
# print("-----Plotting takes {:.4f}s".format(t_plt - t_done))
