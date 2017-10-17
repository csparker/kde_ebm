# Authors: Nicholas C. Firth <ncfirth87@gmail.com>
# License: TBC
from scipy import optimize
import numpy as np
from ..distributions import gaussian


class MixtureModel():
    """Wraps up two distributions and the mixture parameter.

    Attributes
    ----------
    dModel : distribution
        Distribution object to use for the diseased data.
    hModel : distribution
        Distribution object to use for the healthy data.
    mix : float
        Mixing fraction, as percent of healthy patients.
    """
    def __init__(self, cn_comp=None, ad_comp=None, mixture=None):
        """Initiate new MixtureModel object

        Parameters
        ----------
        healthyModel : distribution, optional
            Distribution object to use for the healthy data.
        diseaseModel : TYdistributionPE, optional
            Distribution object to use for the diseased data.
        mixture : float, optional
            Mixing fraction, as percent of healthy patients.
        """
        self.cn_comp = cn_comp
        self.ad_comp = ad_comp
        self.mix = mixture

    def likelihood(self, theta, X):
        """"Calculates the likelihood of the data given the model
        parameters scored in theta. theta should contain normal mean,
        normal standard deviation, abnormal mean, abnormal standard
        deviation and the fraction of the data that is normal

        Parameters
        ----------
        theta : array-like, shape(5,)
            List containing the parameters required for a mixture model.
            [hModelMu, hModelSig, dModelMu, dModelSig, mixture]
        inData : array-like, shape(numPatients,)
            Biomarker measurements for patients.

        Returns
        -------
        likelihood : float
            Negative log likelihood of the data given the parameters theta.
        """
        # thetaNums allows us to use other distributions with a varying
        # number of paramters. Not included in this version of the code.

        # if len(theta[np.isnan(theta)]:
            # return 1e100
        if np.isnan(X.sum()):
            raise ValueError('NaN in likelihood')
        if np.isnan(theta.sum()):
            return 1e100
        n_cn_params = self.cn_comp.n_params
        n_ad_params = self.ad_comp.n_params
        cn_theta = theta[:n_cn_params]
        ad_theta = theta[n_cn_params:n_cn_params+n_ad_params]
        mixture = theta[-1]

        self.cn_comp.set_theta(cn_theta)
        self.ad_comp.set_theta(ad_theta)

        cn_pdf = self.cn_comp.pdf(X)*mixture
        ad_pdf = self.ad_comp.pdf(X)*(1-mixture)

        data_likelihood = cn_pdf + ad_pdf
        data_likelihood[data_likelihood == 0] = np.finfo(float).eps
        data_likelihood = np.log(data_likelihood)
        return -1*np.sum(data_likelihood)

    def fixed_cn_likelihood(self, ad_theta, X):
        theta = np.concatenate((self.cn_comp.get_theta(), ad_theta))
        return self.likelihood(theta, X)

    def fixed_ad_likelihood(self, ad_theta, X):
        raise NotImplementedError('Fixed ad component not yet needed')

    def probability(self, X):
        """Get the probability of some data based on the mixture model

        Parameters
        ----------
        inData : array-like, shape(numPatients,)
            Biomarker measurements for patients.

        Returns
        -------
        hProb : array-like, shape(numPatients, 2)
            Probability of patients biomarkers being normal according to the
            MixtureModel.
        dProb : array-like, shape(numPatients, 2)
            Probability of patients biomarkers being abnormal according to the
            MixtureModel.
        """
        nan_mask = np.isnan(X)
        out_prob = np.empty(X.shape)
        cn_likelihood = self.cn_comp.pdf(X[~nan_mask])
        ad_likelihood = self.ad_comp.pdf(X[~nan_mask])

        err_mask = (cn_likelihood == 0) & (ad_likelihood == 0)
        cn_likelihood[err_mask] = 1
        ad_likelihood[err_mask] = 1

        out_prob[~nan_mask] = cn_likelihood/(cn_likelihood+ad_likelihood)
        out_prob[nan_mask] = .5
        return out_prob

    def fit(self, X, y):
        """This will fit a mixture model to some given data. Labelled data
        is used to derive starting conditions for the optimize function,
        labels are 0 for normal and 1 for abnormal. The model type corresponds
        to the type of distributions used, currently there is normal and
        uniform distributions. Be careful when chosing distributions as the
        optimiser can throw out NaNs.

        Parameters
        ----------
        X : array-like, shape(numPatients,)
            Biomarker measurements for patients.
        y : array-like, shape(numPatients,)
            Diagnosis labels for each of the patients.

        Returns
        -------
        mixInfoOutput : array-like, shape(5,)
            List containing the parameters required for a mixture model.
            [hModelMu, hModelSig, dModelMu, dModelSig, mixture]
        """
        event_sign = np.nanmean(X[y == 0]) < np.nanmean(X[y == 1])
        opt_bounds = []
        opt_bounds += self.cn_comp.get_bounds(X, X[y == 0], event_sign)
        opt_bounds += self.ad_comp.get_bounds(X, X[y == 1], not event_sign)
        # Magic number
        opt_bounds += [(0.1, 0.9)]
        init_params = []
        init_params += self.cn_comp.estimate_params(X[y == 0])
        init_params += self.ad_comp.estimate_params(X[y == 1])
        # Magic number
        init_params += [0.5]
        res = optimize.minimize(self.likelihood,
                                init_params, args=(X[~np.isnan(X)],),
                                bounds=opt_bounds,
                                method='SLSQP')
        res = res.x
        if np.isnan(res.sum()):
            res = optimize.minimize(self.likelihood,
                                    init_params, args=(X[~np.isnan(X)],),
                                    bounds=opt_bounds)
            res = res.x
        n_cn_params = self.cn_comp.n_params
        n_ad_params = self.ad_comp.n_params
        self.cn_comp.set_theta(res[:n_cn_params])
        self.ad_comp.set_theta(res[n_cn_params:n_cn_params+n_ad_params])
        self.mix = res[-1]
        return res

    def fit_constrained(self, X, y, fixed_component=None):
        if fixed_component is not None:
            raise NotImplementedError('Only cn can be fixed currently')

        event_sign = np.nanmean(X[y == 0]) < np.nanmean(X[y == 1])

        cn_est = self.cn_comp.estimate_params(X[y == 0])
        self.cn_comp.set_theta(cn_est)

        opt_bounds = self.ad_comp.get_bounds(X, X[y == 1], not event_sign)
        # magic number
        opt_bounds += [(0.1, 0.9)]
        init_params = self.ad_comp.estimate_params(X[y == 1])
        # magic number
        init_params += [0.5]
        self.fixed_cn_likelihood(init_params, X[~np.isnan(X)])
        res = optimize.minimize(self.fixed_cn_likelihood,
                                init_params, args=(X[~np.isnan(X)],),
                                bounds=opt_bounds,
                                method='SLSQP')
        res = res.x
        if np.isnan(res.sum()):
            res = optimize.minimize(self.fixed_cn_likelihood,
                                    init_params, args=(X[~np.isnan(X)],),
                                    bounds=opt_bounds)
            res = res.x
        self.ad_comp.set_theta(res[:-1])
        self.mix = res[-1]
        return res


def get_prob_mat(X, mixture_models):
    """Gives the matrix of probabilities that a patient has normal/abnormal
    measurements for each of the biomarkers. Output is number of patients x
    number of biomarkers x 2.

    Parameters
    ----------
    X : array-like, shape(numPatients, numBiomarkers)
        All patient-all biomarker measurements.
    y : array-like, shape(numPatients,)
        Diagnosis labels for each of the patients.
    mixtureModels : array-like, shape(numBiomarkers,)
        List of fit mixture models for each of the biomarkers.

    Returns
    -------
    outProbs : array-like, shape(numPatients, numBioMarkers, 2)
        Probability for a normal/abnormal measurement in all biomarkers
        for all patients (and controls).
    """

    prob_mat = np.empty((X.shape[0], X.shape[1], 2))
    for i in range(X.shape[1]):
        prob_mat[:, i, 0] = mixture_models[i].probability(X[:, i])
    prob_mat[:, :, 1] = 1-prob_mat[:, :, 0]
    return prob_mat


def fit_all_gmm_models(X, y):
    n_particp, n_biomarkers = X.shape
    mixture_models = []
    for i in range(n_biomarkers):
        bio_y = y[~np.isnan(X[:, i])]
        bio_X = X[~np.isnan(X[:, i]), i]
        cn_comp = gaussian.Gaussian()
        ad_comp = gaussian.Gaussian()
        mm = MixtureModel(cn_comp, ad_comp)
        mm.fit(bio_X, bio_y)
        mixture_models.append(mm)
    return mixture_models
