# Authors: Nicholas C. Firth <ncfirth87@gmail.com>
# License: TBC
from ..event_order import EventOrder
from ..mixture_model import get_prob_mat, fit_all_gmm_models, fit_all_kde_models
from multiprocessing import Pool, cpu_count
from ..plotting import mixture_model_grid, mcmc_trace, greedy_ascent_trace
import numpy as np


def greedy_ascent_creation(prob_mat, n_iter=1000, n_init=10):
    n_biomarkers = prob_mat.shape[1]
    starts_dict = dict((x, []) for x in range(n_init))
    for start_idx in range(n_init):
        current_order = EventOrder(n_biomarkers=n_biomarkers)
        current_order.score_ordering(prob_mat)
        starts_dict[start_idx].append(current_order)
        for iter_n in range(1, n_iter):
            new_order = current_order.swap_events()
            new_order.score_ordering(prob_mat)
            if new_order > current_order:
                current_order = new_order
            starts_dict[start_idx].append(current_order)
    return starts_dict


def mcmc(X, mixture_models, n_iter=10000, greedy_n_iter=1000,
         greedy_n_init=10, plot=True):
    prob_mat = get_prob_mat(X, mixture_models)
    greedy_dict = greedy_ascent_creation(prob_mat,
                                         greedy_n_iter,
                                         greedy_n_init)
    if plot:
        fig, ax = greedy_ascent_trace(greedy_dict)
        fig.show()
    current_order = greedy_dict[0][-1]
    for i in range(1, greedy_n_init):
        new_order = greedy_dict[i][-1]
        if new_order > current_order:
            current_order = new_order
    mcmc_samples = [current_order]
    for i in range(1, n_iter):
        new_order = current_order.swap_events()
        new_order.score_ordering(prob_mat)
        if new_order - current_order > 100:
            ratio = 1
        else:
            ratio = np.exp(new_order - current_order)
        if ratio > np.random.random():
            current_order = new_order
        mcmc_samples.append(current_order)
    mcmc_samples.sort(reverse=True)
    return mcmc_samples


def create_bootstrap(X, y):
    #if np.bincount(y).shape[0] > 2:
    #    raise NotImplementedError(('Only binary labels'
    #                               'are currently supported'))
    n_particp, n_biomarkers = X.shape
    boot_X = np.empty(X.shape)
    boot_y = np.empty(y.shape, dtype='int32')
    idxs = np.arange(y.shape[0])

    #for i in range(2):
    y_u = np.unique(y)
    for i in range(len(y_u)):
        sample = np.random.choice(idxs[y == y_u[i]])
        boot_X[i, :] = X[sample, :]
        boot_y[i] = y[sample]
    samples = np.random.choice(idxs, size=y.shape[0]-len(y_u))
    boot_X[len(y_u):, :] = X[samples, :]
    boot_y[len(y_u):] = y[samples]
    iqr = np.nanpercentile(boot_X, 75, axis=0)
    iqr -= np.nanpercentile(boot_X, 25, axis=0)
    if np.any(iqr == 0):
        return create_bootstrap(X, y)
    return boot_X, boot_y

# def create_bootstrap_fixed(X, y):
#     y2 = y[y<2]
#     X2 = X[y<2]
#     if np.bincount(y2).shape[0] > 2:
#         raise NotImplementedError(('Only binary labels'
#                                    'are currently supported'))
#     n_particp, n_biomarkers = X.shape
#     boot_X = np.empty(X.shape)
#     boot_y = np.empty(y.shape, dtype='int32')
#     idxs = np.arange(y2.shape[0])
#
#     for i in range(2):
#         sample = np.random.choice(idxs[y2 == i])
#         boot_X[i, :] = X2[sample, :]
#         boot_y[i] = y2[sample]
#     samples = np.random.choice(idxs, size=y.shape[0]-2)
#     boot_X[2:, :] = X2[samples, :]
#     boot_y[2:] = y2[samples]
#     iqr = np.nanpercentile(boot_X, 75, axis=0)
#     iqr -= np.nanpercentile(boot_X, 25, axis=0)
#     if np.any(iqr == 0):
#         return create_bootstrap_fixed(X, y)
#     return boot_X, boot_y


def bootstrap_ebm(X, y, n_bootstrap=32, n_mcmc_iter=10000,
                  score_names=None, plot=False,
                  kde_flag=True,
                  **kwargs):
    bootstrap_samples = []
    for i in range(n_bootstrap):
        print('Bootstrap {0} of {1}: refitting mixtures'.format(i+1,n_bootstrap))
        boot_X, boot_y = create_bootstrap(X, y)
        # Choose which MM to use
        if kde_flag:
            mixtures = fit_all_kde_models(boot_X, boot_y)
        else:
            mixtures = fit_all_gmm_models(boot_X, boot_y)
        mcmc_samples = mcmc(boot_X, mixtures, n_iter=n_mcmc_iter,
                            plot=False, **kwargs)
        bootstrap_samples += mcmc_samples
        if plot:
            fig, ax = mixture_model_grid(boot_X, boot_y,
                                         mixtures, score_names)
            fig.savefig('Bootstrap{}_mixtures.png'.format(i+1))
            fig.close()
            fig, ax = mcmc_trace(mcmc_samples)
            fig.savefig('Bootstrap{}_mcmc_trace.png'.format(i+1))
            fig.close()
    return bootstrap_samples

#* Added by Neil Oxtoby, June 2018 - bootstrapping of the sequence only, not the MM
def bootstrap_ebm_fixedMM(X, y, n_bootstrap=32, n_mcmc_iter=10000,
                          score_names=None, plot=False, 
                          kde_flag=True,
                          mix_mod=False,
                          **kwargs):
    bootstrap_samples = []
    for i in range(n_bootstrap):
        boot_X, boot_y = create_bootstrap(X, y)
        if isinstance(mix_mod,bool):
            print('Bootstrap {0} of {1}: refitting mixtures'.format(i+1,n_bootstrap))
            if kde_flag:
                mixtures = fit_all_kde_models(boot_X, boot_y)
            else:
                mixtures = fit_all_gmm_models(boot_X, boot_y)
        else:
            print('Bootstrap {0} of {1}: not refitting KDE mixtures'.format(i+1,n_bootstrap))
            mixtures = mix_mod
        mcmc_samples = mcmc(boot_X, mixtures, n_iter=n_mcmc_iter,
                            plot=False, **kwargs)
        bootstrap_samples += mcmc_samples
        if(plot):
            fig, ax = mixture_model_grid(boot_X, boot_y,
                                         mixtures, score_names)
            fig.savefig('Bootstrap{}_mixtures.png'.format(i+1))
            fig.close()
            fig, ax = mcmc_trace(mcmc_samples)
            fig.savefig('Bootstrap{}_mcmc_trace.png'.format(i+1))
            fig.close()
    return bootstrap_samples

def parallel_bootstrap(X, y, n_bootstrap=50,
                        n_processes=-1):
    bootstrap_samples = []
    for i in range(n_bootstrap):
        bootstrap_samples.append(create_bootstrap(X, y))
    if n_processes == -1:
        n_processes = cpu_count()
    pool = Pool(processes=n_processes)
    mcmc_samples = pool.map(parallel_bootstrap_, bootstrap_samples)
    samples_formatted = []
    for i in range(n_bootstrap):
        samples_formatted += mcmc_samples[0]
        del mcmc_samples[0]
    return samples_formatted


def parallel_bootstrap_(Xy, kde_flag=True):
    boot_X, boot_y = Xy
    if kde_flag:
        mixtures = fit_all_kde_models(boot_X, boot_y)
    else:
        mixtures = fit_all_gmm_models(boot_X, boot_y)
    mcmc_samples = mcmc(boot_X, mixtures, plot=False)
    return mcmc_samples