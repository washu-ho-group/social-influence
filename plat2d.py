from __future__ import division
import numpy as np


class Platform(object):
    """Abstract base class for the platform in 2d dimension
    A platform is an environment where users interacts with items.
    Property:
        int num_item
        int num_user
        np.ndarray items
        np.ndarray viewHistory
        np.ndarray evalHistory
        np.ndarray itemRanking
        np.ndarray itemPlacement
        list perfmeas
    Function:
        rankItems()
        placeItems()
        run()
    """

    def __init__(self, items, users):
        self.num_item = len(items)
        self.num_user = len(users)
        self.items = np.zeros((5, self.num_item))
        for k, v in items.items():
            self.items[0, k] = v.getQuality()
            self.items[1, k] = v.getViews()
            self.items[2, k] = v.getUpVotes()
            self.items[3, k] = v.getDownVotes()
        # rows: quality, views, upvotes, downvotes, ranking
        self.users = users
        # self.viewHistory = np.zeros((self.num_item, self.num_user))
        # self.evalHistory = np.zeros((self.num_item, self.num_user))
        self.itemRanking = np.zeros(self.num_item)
        self.itemPlacement = np.zeros(self.num_item)
        self.perfmeas = []
        self.true_happiness = np.zeros(self.num_user)

    def rankItems(self, mode='random', c=1):
        # Rank items with given mode of ranking policies from
        # ['random', 'quality', 'views', 'popularity', 'upvotes', 'ucb', 'lcb']
        if mode == 'random':
            ranking = np.arange(self.num_item)
            np.random.shuffle(ranking)
        elif mode == 'quality':
            ranking = np.argsort(-self.items[0])
        elif mode == 'views':
            ranking = np.argsort(-self.items[1])
        elif mode == 'popularity':
            ranking = np.argsort(-self.items[2])
        elif mode == 'upvotes':
            ratio = np.true_divide(self.items[2], self.items[1])
            ranking = np.argsort(-ratio)
        elif mode == 'lcb':
            lower = confidenceBound(self.items, self.num_user, c)[0]
            ranking = np.argsort(-lower)
        elif mode == 'ucb':
            upper = confidenceBound(self.items, self.num_user, c)[1]
            ranking = np.argsort(-upper)
        else:
            raise Exception("Unexpected rank mode")
        self.itemRanking = ranking
        self.items[-1] = np.argsort(ranking)
        return ranking

    def placeItems(self, mode='all'):
        if mode == 'all':
            placement = self.itemRanking
        else:
            raise Exception("Unexpected place mode")
        self.itemPlacement = placement
        return placement

    def run(self,
            rankMode='random',
            viewMode='first',
            evalMethod='majority_bias',
            perf=[True, True, True],
            perfmeasK=10,
            numFree=1,
            n_showed=1,
            p_pos=1,
            user_c=1,
            tau=1,
            c=1):
        # Run a simulation with given mode of viewing policies from
        # ['first', 'position']
        # Initialization
        self.rankItems(mode=rankMode, c=c)
        self.placeItems(mode='all')
        self.true_happiness = np.zeros(self.num_user)
        # Ranking in descending quality order
        desq_rank = np.argsort(-self.items[0])
        expected_top_K = desq_rank[0:perfmeasK]
        # Run Start
        if viewMode == 'position':
            # positional preference (from CVP)
            if n_showed > 1 or n_showed < 0:
                portion_showed = 1
            else:
                portion_showed = n_showed
            num_showed = int(self.num_item*portion_showed)
            display_rank = np.arange(num_showed)
            popularity = (1 / (1 + display_rank))**tau
            popularity = popularity / np.sum(popularity)

        for uid in range(self.num_user):
            if viewMode == 'position':
                popMask = self.itemRanking[:num_showed]
                lower = confidenceBound(self.items[:, popMask], self.num_user,
                                        user_c)[0]
                lcbRank = np.argsort(-lower)
                lcbMask = popMask[np.argsort(lcbRank)]
                viewProb = np.zeros((self.num_item, ))
                viewProb[popMask] += p_pos * popularity
                viewProb[lcbMask] += (1 - p_pos) * popularity
                iid = np.random.choice(self.num_item, p=viewProb)
            else:
                iid = self.itemRanking[0]

            # self.viewHistory[iid][uid] += 1
            self.items[1, iid] += 1

            if evalMethod == "abs_quality":
                evaluation = self.items[0, iid]
            elif evalMethod == "rel_quality":
                evaluation = self.items[0, iid] + np.random.normal(0, 0.1)
            elif evalMethod == "upvote_only":
                evaluation = 1 if np.random.rand() < self.items[0, iid] else -1
            else: # "majority_bias" (from CVP)
                q = self.items[0, iid]
                r = np.true_divide(self.items[2, iid], self.items[1, iid])
                g = .1 * r + .1 * (1 - r)
                p = np.exp(q + g) / (1 + np.exp(q + g))
                evaluation = 1 if np.random.rand() < p else -1
            if evaluation:
                # self.evalHistory[iid][uid] = evaluation
                if evaluation > 0:
                    self.items[2, iid] += 1
                else:
                    self.items[3, iid] += 1

            self.true_happiness[uid] = self.items[0, iid] if uid == 0 else self.true_happiness[uid - 1] + self.items[0, iid]

            ########
            # first few runs random to get initial data
            if uid < 0:
                self.rankItems(mode='random', c=c)
            else:
                self.rankItems(mode=rankMode, c=c)
            ########
            self.placeItems(mode='all')

            time = uid + 1
            perfmea = dict()
            if perf[0]:
                # Happiness
                sum_upvotes = np.sum(self.items[2])
                upvotes_t = sum_upvotes / (time + numFree * self.num_item)
                happy = upvotes_t
                perfmea['happy'] = happy
            if perf[1]:
                # Kendall Tau Distance
                if rankMode == "random":
                    # Reorder the final list in ratio of upvotes order if ranking strategy is random
                    ratio = np.true_divide(self.items[2], self.items[1])
                    final_rank = np.argsort(-ratio)
                else:
                    final_rank = self.itemRanking
                # Calculate the Kendall tau distance
                tau, p_value = stats.kendalltau(desq_rank, final_rank)
                perfmea['ktd'] = tau
            if perf[2]:
                # Top K Percentage
                actual_top_K = final_rank[0:perfmeasK]
                in_top_K = set(expected_top_K).intersection(actual_top_K)
                topK = len(in_top_K) / perfmeasK
                perfmea['topK'] = topK
            # perfmea['items']=self.items
            self.perfmeas.append(perfmea)

        self.true_happiness /= np.arange(self.num_user) + numFree * self.num_item
        return self.perfmeas

    def step(self,
             uid,
             rankMode='random',
             viewMode='first',
             evalMethod='upvote_only',
             numFree=1,
             n_showed=-1,
             p_pos=1,
             user_c=1,
             tau=1,
             c=1):
        # Run a step of simulation with given mode of viewing policies from
        # ['first', 'position']
        # Initialization
        self.rankItems(mode=rankMode, c=c)
        self.placeItems(mode='all')

        # Run Start
        if viewMode == 'position':
            # positional preference (from CVP)
            if n_showed > 1 or n_showed < 0:
                portion_showed = 1
            else:
                portion_showed = n_showed
            num_showed = int(self.num_item*portion_showed)
            display_rank = np.arange(num_showed)
            popularity = (1 / (1 + display_rank))**tau
            popularity = popularity / np.sum(popularity)

        if viewMode == 'position':
            popMask = self.itemRanking[:num_showed]
            lower = confidenceBound(self.items[:, popMask], self.num_user,
                                    user_c)[0]
            lcbRank = np.argsort(-lower)
            lcbMask = popMask[np.argsort(lcbRank)]
            viewProb = np.zeros((self.num_item, ))
            viewProb[popMask] += p_pos * popularity
            viewProb[lcbMask] += (1 - p_pos) * popularity
            iid = np.random.choice(self.num_item, p=viewProb)
        else:
            iid = self.itemRanking[0]

        # self.viewHistory[iid][uid] += 1
        self.items[1, iid] += 1

        if evalMethod == "abs_quality":
            evaluation = self.items[0, iid]
        elif evalMethod == "rel_quality":
            evaluation = self.items[0, iid] + np.random.normal(0, 0.1)
        else:  # "upvote_only":
            evaluation = 1 if np.random.rand() < self.items[0, iid] else -1
        if evaluation:
            # self.evalHistory[iid][uid] = evaluation
            if evaluation > 0:
                self.items[2, iid] += 1
            else:
                self.items[3, iid] += 1

        # Happiness
        time = uid + 1
        sum_upvotes = np.sum(self.items[2])
        upvotes_t = sum_upvotes / (time + numFree * self.num_item)

        return upvotes_t


def confidenceBound(items, T, c=1):
    ratio = np.true_divide(items[2], items[1])
    bound = np.true_divide(np.log(T), items[1])
    bound = c * np.sqrt(bound)
    lower = ratio - bound
    upper = ratio + bound
    return (lower, upper)
