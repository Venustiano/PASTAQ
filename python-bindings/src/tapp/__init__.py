import math

from .tapp import *
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.optimize import curve_fit
import matplotlib.colors as colors
from matplotlib.patches import Ellipse
import os
# TODO: Use pathlib instead of os?
# from pathlib import Path

# TODO(alex): Write documentation.


def tic(raw_data, min_rt=-math.inf, max_rt=math.inf):
    rt = []
    intensity = []
    for i in range(0, len(raw_data.scans)):
        if (raw_data.scans[i].retention_time < min_rt or
                raw_data.scans[i].retention_time > max_rt):
            continue
        sum = 0
        for j in range(0, raw_data.scans[i].num_points):
            sum = sum + raw_data.scans[i].intensity[j]
        intensity = intensity + [sum]
        rt = rt + [raw_data.scans[i].retention_time]

    return (rt, intensity)


def load_example_data():
    raw_data = read_mzxml(
        '/data/toydata/toy_data.mzXML',
        instrument_type='orbitrap',
        resolution_ms1=70000,
        resolution_msn=30000,
        reference_mz=200,
        fwhm_rt=9,
        polarity='pos',
        min_mz=801,
        max_mz=803,
        min_rt=2808,
        max_rt=2928,
    )
    # raw_data = read_mzxml(
    # '/data/ftp_data/150210_11_01.mzXML',
    # instrument_type = 'orbitrap',
    # resolution_ms1 = 70000,
    # resolution_msn = 30000,
    # reference_mz = 200,
    # polarity = 'pos',
    # min_mz = 400,
    # max_mz = 1000,
    # min_rt = 2000,
    # max_rt = 4000,
    # )
    # raw_data = read_mzxml(
    # '/data/qatar/17122018/mzXML/Acute2U_3001.mzXML',
    # instrument_type = 'orbitrap',
    # resolution_ms1 = 70000,
    # resolution_msn = 30000,
    # reference_mz = 200,
    # fwhm_rt = 9,
    # polarity = 'pos',
    # )
    return raw_data

# NOTE: This is not the best design for this function and could be greatly improved.


def plot_mesh(mesh, transform='sqrt', figure=None):
    plt.style.use('dark_background')
    plt.ion()
    plt.show()

    if figure is None:
        figure = plt.figure()

    img = mesh.data
    img = np.reshape(img, (mesh.m, mesh.n))
    bins_rt = mesh.bins_rt
    bins_mz = mesh.bins_mz
    num_bins_mz = len(bins_mz)
    num_bins_rt = len(bins_rt)
    min_mz = np.array(bins_mz).min()
    max_mz = np.array(bins_mz).max()
    min_rt = np.array(bins_rt).min()
    max_rt = np.array(bins_rt).max()

    plt.figure(figure.number)
    plt.clf()
    gs = gridspec.GridSpec(5, 5)
    mz_plot = plt.subplot(gs[0, :-1])
    mz_plot.clear()
    mz_plot.plot(bins_mz, img.sum(axis=0))
    mz_plot.margins(x=0)
    mz_plot.set_xticks([])
    mz_plot.set_ylabel("Intensity")

    rt_plot = plt.subplot(gs[1:, -1])
    rt_plot.plot(img.sum(axis=1), bins_rt)
    rt_plot.margins(y=0)
    rt_plot.set_yticks([])
    rt_plot.set_xlabel("Intensity")

    img_plot = plt.subplot(gs[1:, :-1])
    offset_rt = (np.array(mesh.bins_rt).max() - np.array(mesh.bins_rt).min())/mesh.m / 2
    offset_mz = (np.array(mesh.bins_mz).max() - np.array(mesh.bins_mz).min())/mesh.n / 2
    if transform == 'sqrt':
        img_plot.pcolormesh(
                np.array(mesh.bins_mz) - offset_mz,
                np.array(mesh.bins_rt) - offset_rt,
                img,
                snap=True,
                norm=colors.PowerNorm(gamma=1./2.))
    elif transform == 'cubic':
        img_plot.pcolormesh(
                np.array(mesh.bins_mz) - offset_mz,
                np.array(mesh.bins_rt) - offset_rt,
                img,
                norm=colors.PowerNorm(gamma=1./3.))
    elif transform == 'log':
        img_plot.pcolormesh(
                np.array(mesh.bins_mz) - offset_mz,
                np.array(mesh.bins_rt) - offset_rt,
                img,
                norm=colors.LogNorm(vmin=img.min()+1e-8, vmax=img.max()))
    else:
        img_plot.pcolormesh(mesh.bins_mz, mesh.bins_rt, img)
    
    img_plot.set_xlim([np.array(mesh.bins_mz).min() - offset_mz, np.array(mesh.bins_mz).max() - offset_mz])
    img_plot.set_ylim([np.array(mesh.bins_rt).min() - offset_rt, np.array(mesh.bins_rt).max() - offset_rt])

    img_plot.set_xlabel("m/z")
    img_plot.set_ylabel("retention time (s)")

    return({
        "img_plot": img_plot,
        "mz_plot": mz_plot,
        "rt_plot": rt_plot,
    })


def find_scan_indexes(raw_data, peak_candidate):
    # Find min/max scans.
    rts = np.array([scan.retention_time for scan in raw_data.scans])
    scan_idx = np.where((rts >= peak_candidate['roi_min_rt']) & (
        rts <= peak_candidate['roi_max_rt']))[0]
    return scan_idx


def find_mz_indexes(raw_data, peak_candidate, scan_idx):
    mz_idx = []
    for j in scan_idx:
        scan = raw_data.scans[j]
        mz_i = np.where(np.array(
            (scan.mz >= peak_candidate['roi_min_mz']) &
            (scan.mz <= peak_candidate['roi_max_mz'])))[0]
        mz_idx = mz_idx + [mz_i]
    return mz_idx


def find_raw_points_py(raw_data, scan_idx, mz_idx):
    mzs = []
    rts = []
    intensities = []
    for i in range(0, len(scan_idx)):
        scan = raw_data.scans[scan_idx[i]]
        mzs = mzs + [scan.mz[j] for j in mz_idx[i]]
        intensities = intensities + [scan.intensity[j] for j in mz_idx[i]]
        rts = np.concatenate(
            [rts, np.repeat(scan.retention_time, len(mz_idx[i]))])
    return (np.array(mzs), np.array(intensities), np.array(rts))


def gaus(x, a, x0, sigma):
    return a * np.exp(-(x - x0)**2 / (2 * sigma**2))


def gaus2d(X, a, x_0, sigma_x, y_0, sigma_y):
    x = X[0]
    y = X[1]
    return a * np.exp(-0.5 * ((x - x_0) / sigma_x) ** 2) * np.exp(-0.5 * ((y - y_0)/sigma_y) ** 2)


def fit_curvefit(mzs, intensities, rts):
    X = np.array([mzs, rts])
    mean_x = sum(X[0] * intensities) / sum(intensities)
    sigma_x = np.sqrt(sum(intensities * (X[0] - mean_x)**2) / sum(intensities))
    mean_y = sum(X[1] * intensities) / sum(intensities)
    sigma_y = np.sqrt(sum(intensities * (X[1] - mean_y)**2) / sum(intensities))
    fitted_parameters, pcov_2d = curve_fit(gaus2d, X, intensities, p0=[
                                           max(intensities), mean_x, sigma_x, mean_y, sigma_y])
    return fitted_parameters

# NOTE: Testing different fitting methods


def generate_gaussian():
    x = np.linspace(801.38, 801.42, 100)
    y = gaus(x, 1, 801.40, 0.0025)
    # x = x - x.mean()
    return (x, y)

# NOTE: Testing different fitting methods


def fit_inle(x, y):
    mean_x = np.sum(x * y) / np.sum(y)
    sigma_x = np.sqrt(sum(y * (x - mean_x)**2) / sum(y))
    fitted_parameters, cov = curve_fit(gaus, x, y, p0=[max(y), mean_x, sigma_x])
    return fitted_parameters


def fit_caruana(x, y):
    x_mean = x.mean()
    x = x - x_mean
    X = np.array(
        [
            [len(x), np.array(x).sum(), np.power(x, 2).sum()],
            [np.array(x).sum(), np.power(x, 2).sum(), np.power(x, 3).sum()],
            [np.power(x, 2).sum(), np.power(x, 3).sum(), np.power(x, 4).sum()]
        ],
    )
    Y = np.array([
        np.log(y).sum(),
        (x * np.log(y)).sum(),
        (np.power(x, 2) * np.log(y)).sum()
    ])
    a, b, c = np.linalg.solve(X, Y)
    mean = -b / (2 * c) + x_mean
    sigma = np.sqrt(-1 / (2 * c))
    height = np.exp(a - (b ** 2) / (4 * c))
    # print(np.allclose(np.dot(X, A), Y))
    return np.array([height, mean, sigma])


def fit_guos(x, y):
    x_mean = x.mean()
    x = x - x_mean
    X = np.array(
        [
            [
                np.power(y, 2).sum(),
                (x * np.power(y, 2)).sum(),
                (np.power(x, 2) * np.power(y, 2)).sum(),
            ],
            [
                (x * np.power(y, 2)).sum(),
                (np.power(x, 2) * np.power(y, 2)).sum(),
                (np.power(x, 3) * np.power(y, 2)).sum(),
            ],
            [
                (np.power(x, 2) * np.power(y, 2)).sum(),
                (np.power(x, 3) * np.power(y, 2)).sum(),
                (np.power(x, 4) * np.power(y, 2)).sum(),
            ],
        ],
    )
    Y = np.array([
        (np.power(y, 2) * np.log(y)).sum(),
        (np.power(y, 2) * x * np.log(y)).sum(),
        (np.power(y, 2) * np.power(x, 2) * np.log(y)).sum()
    ])
    a, b, c = np.linalg.solve(X, Y)
    mean = -b / (2 * c) + x_mean
    sigma = np.sqrt(-1 / (2 * c))
    height = np.exp(a - (b ** 2) / (4 * c))
    # print(np.allclose(np.dot(X, A), Y))
    return np.array([height, mean, sigma])


def fit_guos_2d(x, y, z):
    x_mean = x.mean()
    x = x - x_mean
    y_mean = y.mean()
    y = y - y_mean

    z_2 = np.power(z, 2)
    x_2 = np.power(x, 2)
    x_3 = np.power(x, 3)
    x_4 = np.power(x, 4)
    y_2 = np.power(y, 2)
    y_3 = np.power(y, 3)
    y_4 = np.power(y, 4)

    X = np.array(
        [
            [
                z_2.sum(),
                (x * z_2).sum(),
                (x_2 * z_2).sum(),
                (y * z_2).sum(),
                (y_2 * z_2).sum(),
            ],
            [
                (x * z_2).sum(),
                (x_2 * z_2).sum(),
                (x_3 * z_2).sum(),
                (x * y * z_2).sum(),
                (x * y_2 * z_2).sum(),
            ],
            [
                (x_2 * z_2).sum(),
                (x_3 * z_2).sum(),
                (x_4 * z_2).sum(),
                (x_2 * y * z_2).sum(),
                (x_2 * y_2 * z_2).sum(),
            ],
            [
                (y * z_2).sum(),
                (x * y * z_2).sum(),
                (x_2 * y * z_2).sum(),
                (y_2 * z_2).sum(),
                (y_3 * z_2).sum(),
            ],
            [
                (y_2 * z_2).sum(),
                (x * y_2 * z_2).sum(),
                (x_2 * y_2 * z_2).sum(),
                (y_3 * z_2).sum(),
                (y_4 * z_2).sum(),
            ],
        ],
    )
    Y = np.array([
        (z_2 * np.log(z)).sum(),
        (z_2 * x * np.log(z)).sum(),
        (z_2 * x_2 * np.log(z)).sum(),
        (z_2 * y * np.log(z)).sum(),
        (z_2 * y_2 * np.log(z)).sum(),
    ])
    # a, b, c, d, e = np.linalg.solve(X, Y)
    beta = np.linalg.lstsq(X, Y)
    a, b, c, d, e = beta[0]

    sigma_mz = np.sqrt(1/(-2 * c))
    mz = b / (-2 * c) + x_mean
    sigma_rt = np.sqrt(1/(-2 * e))
    rt = d / (-2 * e) + y_mean
    height = np.exp(a - ((b ** 2) / (4 * c)) - ((d ** 2) / (4 * e)))

    # print(np.allclose(np.dot(X, A), Y))
    return np.array([height, mz, sigma_mz, rt, sigma_rt])

def fit_weighted_guos_2d(x, y, z, x_local_max, y_local_max, theoretical_sigma_mz, theoretical_sigma_rt):
    x = x - x_local_max
    y = y - y_local_max

    a_0_0 = 0
    a_0_1 = 0
    a_0_2 = 0
    a_0_3 = 0
    a_0_4 = 0
    a_1_0 = 0
    a_1_1 = 0
    a_1_2 = 0
    a_1_3 = 0
    a_1_4 = 0
    a_2_0 = 0
    a_2_1 = 0
    a_2_2 = 0
    a_2_3 = 0
    a_2_4 = 0
    a_3_0 = 0
    a_3_1 = 0
    a_3_2 = 0
    a_3_3 = 0
    a_3_4 = 0
    a_4_0 = 0
    a_4_1 = 0
    a_4_2 = 0
    a_4_3 = 0
    a_4_4 = 0
    c_0 = 0
    c_1 = 0
    c_2 = 0
    c_3 = 0
    c_4 = 0
    for i, intensity in enumerate(z):
        mz = x[i] 
        rt = y[i] 
        w = gaus2d([mz, rt], 1, 0, theoretical_sigma_mz, 0, theoretical_sigma_rt)
        w_2 = w * w

        a_0_0 += w_2
        a_0_1 += w_2 * mz
        a_0_2 += w_2 * mz * mz
        a_0_3 += w_2 * rt
        a_0_4 += w_2 * rt * rt

        a_1_0 += w_2 * mz
        a_1_1 += w_2 * mz * mz
        a_1_2 += w_2 * mz * mz * mz
        a_1_3 += w_2 * rt * mz
        a_1_4 += w_2 * rt * rt * mz

        a_2_0 += w_2 * mz * mz
        a_2_1 += w_2 * mz * mz * mz
        a_2_2 += w_2 * mz * mz * mz * mz
        a_2_3 += w_2 * rt * mz * mz
        a_2_4 += w_2 * rt * rt * mz * mz

        a_3_0 += w_2 * rt
        a_3_1 += w_2 * mz * rt 
        a_3_2 += w_2 * mz * mz * rt
        a_3_3 += w_2 * rt * rt
        a_3_4 += w_2 * rt * rt * rt

        a_4_0 += w_2 * rt * rt
        a_4_1 += w_2 * mz * rt * rt 
        a_4_2 += w_2 * mz * mz * rt * rt
        a_4_3 += w_2 * rt * rt * rt
        a_4_4 += w_2 * rt * rt * rt * rt

        c_0 += w_2 * np.log(intensity)
        c_1 += w_2 * np.log(intensity) * mz
        c_2 += w_2 * np.log(intensity) * mz * mz
        c_3 += w_2 * np.log(intensity) * rt
        c_4 += w_2 * np.log(intensity) * rt * rt

    X = np.array(
        [
            [
                a_0_0,
                a_0_1,
                a_0_2,
                a_0_3,
                a_0_4,
            ],
            [
                a_1_0,
                a_1_1,
                a_1_2,
                a_1_3,
                a_1_4,
            ],
            [
                a_2_0,
                a_2_1,
                a_2_2,
                a_2_3,
                a_2_4,
            ],
            [
                a_3_0,
                a_3_1,
                a_3_2,
                a_3_3,
                a_3_4,
            ],
            [
                a_4_0,
                a_4_1,
                a_4_2,
                a_4_3,
                a_4_4,
            ],
        ],
    )
    Y = np.array([
        c_0,
        c_1,
        c_2,
        c_3,
        c_4,
    ])
    a, b, c, d, e = np.linalg.lstsq(X, Y, rcond=1)[0]

    if c >= 0 or e >= 0:
        return np.array([np.nan, np.nan, np.nan, np.nan, np.nan])

    sigma_mz = np.sqrt(1/(-2 * c))
    mz = b / (-2 * c) + x_local_max
    sigma_rt = np.sqrt(1/(-2 * e))
    rt = d / (-2 * e) + y_local_max
    height = np.exp(a - ((b ** 2) / (4 * c)) - ((d ** 2) / (4 * e)))

    return np.array([height, mz, sigma_mz, rt, sigma_rt])

def fit_weighted_guos_2d_constrained(x, y, z, x_local_max, y_local_max, theoretical_sigma_mz, theoretical_sigma_rt):
    x = x - x_local_max
    y = y - y_local_max

    a_0_0 = 0
    a_0_2 = 0
    a_0_4 = 0
    a_2_0 = 0
    a_2_2 = 0
    a_2_4 = 0
    a_4_0 = 0
    a_4_2 = 0
    a_4_4 = 0
    c_0 = 0
    c_2 = 0
    c_4 = 0
    for i, intensity in enumerate(z):
        mz = x[i] 
        rt = y[i] 
        w = gaus2d([mz, rt], 1, 0, theoretical_sigma_mz, 0, theoretical_sigma_rt)
        w_2 = w * w

        a_0_0 += w_2
        a_0_2 += w_2 * mz * mz
        a_0_4 += w_2 * rt * rt

        a_2_0 += w_2 * mz * mz
        a_2_2 += w_2 * mz * mz * mz * mz
        a_2_4 += w_2 * rt * rt * mz * mz

        a_4_0 += w_2 * rt * rt
        a_4_2 += w_2 * mz * mz * rt * rt
        a_4_4 += w_2 * rt * rt * rt * rt

        c_0 += w_2 * np.log(intensity)
        c_2 += w_2 * np.log(intensity) * mz * mz
        c_4 += w_2 * np.log(intensity) * rt * rt

    X = np.array(
        [
            [
                a_0_0,
                a_0_2,
                a_0_4,
            ],
            [
                a_2_0,
                a_2_2,
                a_2_4,
            ],
            [
                a_4_0,
                a_4_2,
                a_4_4,
            ],
        ],
    )
    Y = np.array([
        c_0,
        c_2,
        c_4,
    ])
    a, c, e = np.linalg.lstsq(X, Y, rcond=1)[0]

    if c >= 0 or e >= 0:
        return np.array([np.nan, np.nan, np.nan, np.nan, np.nan])

    sigma_mz = np.sqrt(1/(-2 * c))
    mz = x_local_max
    sigma_rt = np.sqrt(1/(-2 * e))
    rt = y_local_max
    height = np.exp(a)

    return np.array([height, mz, sigma_mz, rt, sigma_rt])

def test_gaus_fit():
    x, y = generate_gaussian()
    parameters_inle = fit_inle(x, y)
    parameters_guos = fit_guos(x, y)
    parameters_caruana = fit_caruana(x, y)
    print("parameters_inle:", parameters_inle)
    print("parameters_guos:", parameters_guos)
    print("parameters_caruana:", parameters_caruana)
    plt.style.use('dark_background')
    plt.ion()
    plt.show()
    fig = plt.figure()
    plt.scatter(x, y, label='Raw data')
    plt.plot(x, gaus(x, *parameters_inle), label='curve_fit',
             linestyle='--', color='crimson')
    plt.plot(x, gaus(x, *parameters_guos), label='guos')
    plt.plot(x, gaus(x, *parameters_caruana),
             label='caruana', linestyle=':', color='aqua')
    plt.legend(loc='upper left')


def fit(raw_data, peak_candidate):
    scan_idx = find_scan_indexes(raw_data, peak_candidate)
    mz_idx = find_mz_indexes(raw_data, peak_candidate, scan_idx)
    data_points = find_raw_points_py(raw_data, scan_idx, mz_idx)
    fitted_parameters = fit_curvefit(
        data_points[0], data_points[1], data_points[2])
    return fitted_parameters


def fit2(raw_data, peak_candidate):
    data_points = find_raw_points(
        raw_data,
        peak_candidate['roi_min_mz'],
        peak_candidate['roi_max_mz'],
        peak_candidate['roi_min_rt'],
        peak_candidate['roi_max_rt']
    )
    fitted_parameters = fit_curvefit(
        data_points.mz, data_points.intensity, data_points.rt)
    return fitted_parameters


def fit3(raw_data, peak_candidate):
    data_points = find_raw_points(
        raw_data,
        peak_candidate['roi_min_mz'],
        peak_candidate['roi_max_mz'],
        peak_candidate['roi_min_rt'],
        peak_candidate['roi_max_rt']
    )
    return fit_guos_2d(
        np.array(data_points.mz),
        np.array(data_points.rt),
        np.array(data_points.intensity))


def fit_raw_weighted_estimate(raw_data, peak_candidate):
    data_points = find_raw_points(
        raw_data,
        peak_candidate['roi_min_mz'],
        peak_candidate['roi_max_mz'],
        peak_candidate['roi_min_rt'],
        peak_candidate['roi_max_rt']
    )
    mzs = np.array(data_points.mz)
    rts = np.array(data_points.rt)
    intensities = np.array(data_points.intensity)

    mean_x = sum(mzs * intensities) / sum(intensities)
    sigma_x = np.sqrt(sum(intensities * (mzs - mean_x)**2) / sum(intensities))
    mean_y = sum(rts * intensities) / sum(intensities)
    sigma_y = np.sqrt(sum(intensities * (rts - mean_y)**2) / sum(intensities))

    return np.array([intensities.max(), mean_x, sigma_x, mean_y, sigma_y])


def plot_peak_fit(raw_data, peak, fig_mz, fig_rt):
    # PLOTTING
    color = np.random.rand(3, 1).flatten()

    data_points = find_raw_points(
        raw_data,
        peak['roi_min_mz'],
        peak['roi_max_mz'],
        peak['roi_min_rt'],
        peak['roi_max_rt']
    )

    rts = data_points.rt
    mzs = data_points.mz
    intensities = data_points.intensity

    # MZ fit plot.
    sort_idx_mz = np.argsort(mzs)
    fitted_intensity_2d_mz = gaus(
        np.array(mzs)[sort_idx_mz],
        peak['fitted_height'],
        peak['fitted_mz'],
        peak['fitted_sigma_mz'],
    )
    plt.figure(fig_mz.number)
    markerline, stemlines, baseline = plt.stem(np.array(mzs)[sort_idx_mz], np.array(
        intensities)[sort_idx_mz], label='intensities', markerfmt=' ')
    plt.setp(baseline, color=color, alpha=0.5)
    plt.setp(stemlines, color=color, alpha=0.5)
    plt.plot(np.array(mzs)[sort_idx_mz], fitted_intensity_2d_mz,
             linestyle='--', color=color, label='2d_fitting')
    plt.xlabel('m/z')
    plt.ylabel('Intensity')

    # RT fit plot.
    xic_x = np.unique(rts)
    # xic_y_max = []
    # for x,y in zip(rts, intensities):
    # pass
    sort_idx_rt = np.argsort(xic_x)
    fitted_intensity_2d_rt = gaus(
        np.array(xic_x)[sort_idx_rt],
        peak['fitted_height'],
        peak['fitted_rt'],
        peak['fitted_sigma_rt'],
    )
    plt.figure(fig_rt.number)
    plt.plot(np.array(xic_x)[sort_idx_rt],
             fitted_intensity_2d_rt, color=color, linestyle='--')
    # plt.plot(xic_x, xic_y_max, label=str(i), linestyle='-', color=color, alpha=0.5)
    plt.xlabel('retention time (s)')
    plt.ylabel('Intensity')

    return fig_mz, fig_rt


def fit_and_plot(raw_data, peak_candidate):
    data_points = find_raw_points(
        raw_data,
        peak_candidate['roi_min_mz'],
        peak_candidate['roi_max_mz'],
        peak_candidate['roi_min_rt'],
        peak_candidate['roi_max_rt']
    )
    fitted_parameters = fit_curvefit(
        data_points.mz, data_points.intensity, data_points.rt)
    plot_peak_candidate(data_points, fitted_parameters)
    return fitted_parameters


def find_roi(raw_data, local_max, avg_rt_fwhm=10):
    peak_candidates = []
    for i in range(0, len(local_max)):
        selected_peak = local_max.iloc[i]
        theoretical_sigma_mz = theoretical_fwhm(
            raw_data, selected_peak['mz']) / (2 * math.sqrt(2 * math.log(2)))
        theoretical_sigma_rt = avg_rt_fwhm / (2 * math.sqrt(2 * math.log(2)))
        tolerance_mz = 2.5 * theoretical_sigma_mz
        tolerance_rt = 2.5 * theoretical_sigma_rt
        min_mz = selected_peak['mz'] - tolerance_mz
        max_mz = selected_peak['mz'] + tolerance_mz
        min_rt = selected_peak['rt'] - tolerance_rt
        max_rt = selected_peak['rt'] + tolerance_rt

        peak_candidates = peak_candidates + [{
            'i': selected_peak['i'],
            'j': selected_peak['j'],
            'estimated_mz': selected_peak['mz'],
            'estimated_rt': selected_peak['rt'],
            'estimated_height': selected_peak['intensity'],
            'roi_min_mz': min_mz,
            'roi_max_mz': max_mz,
            'roi_min_rt': min_rt,
            'roi_max_rt': max_rt,
        }]

    return peak_candidates


def profile_resample():
    # raw_data = read_mzxml(
        # '/data/toydata/toy_data.mzXML',
        # instrument_type = 'orbitrap',
        # resolution_ms1 = 70000,
        # resolution_msn = 30000,
        # reference_mz = 200,
        # fwhm_rt = 9,
        # polarity = 'pos',
        # min_mz = 801,
        # max_mz = 803,
        # min_rt = 2808,
        # max_rt = 2928,
    # )
    raw_data = read_mzxml(
        '/data/qatar/17122018/mzXML/Acute2U_3001.mzXML',
        instrument_type='orbitrap',
        resolution_ms1=70000,
        resolution_msn=30000,
        reference_mz=200,
        fwhm_rt=9,
        polarity='pos',
        # min_mz = 200,
        # max_mz = 800,
        # min_rt = 0,
        # max_rt = 1000,
    )

    mesh = resample(raw_data, 5, 5, 0.5, 0.5)


def profile_peak_fitting(max_peaks=20):
    print("Loading data...")
    # raw_data = read_mzxml(
    # '/data/qatar/17122018/mzXML/Acute2U_3001.mzXML',
    # instrument_type = 'orbitrap',
    # resolution_ms1 = 70000,
    # resolution_msn = 30000,
    # reference_mz = 200,
    # fwhm_rt = 9,
    # polarity = 'pos',
    # )
    raw_data = read_mzxml(
        '/data/toydata/toy_data.mzXML',
        instrument_type='orbitrap',
        resolution_ms1=70000,
        resolution_msn=30000,
        reference_mz=200,
        fwhm_rt=9,
        polarity='pos',
        min_mz=801,
        max_mz=803,
        min_rt=2808,
        max_rt=2928,
    )

    print("Resampling...")
    mesh = resample(raw_data, 5, 5, 0.5, 0.5)

    print("Saving mesh to disk...")
    mesh.save("mesh.dat")

    print("Finding local maxima in mesh...")
    local_max = find_local_max(mesh)
    local_max = pd.DataFrame(local_max)
    local_max.columns = ['i', 'j', 'mz', 'rt', 'intensity']
    local_max = local_max.sort_values('intensity', ascending=False)
    if max_peaks != math.inf:
        local_max = local_max[0:max_peaks]

    peak_candidates = find_roi(raw_data, local_max, 9)
    fitted_parameters = []
    fitted_peaks = []
    for peak_candidate in peak_candidates:
        try:
            # fitted_parameters = fitted_parameters + [fit(raw_data, peak_candidate)]
            # fitted_parameters = fitted_parameters + [fit2(raw_data, peak_candidate)]
            fitted_parameters = fitted_parameters + \
                [fit3(raw_data, peak_candidate)]
            peak = peak_candidate
            peak['fitted_height'] = fitted_parameters[0]
            peak['fitted_mz'] = fitted_parameters[1]
            peak['fitted_sigma_mz'] = fitted_parameters[2]
            peak['fitted_rt'] = fitted_parameters[3]
            peak['fitted_sigma_rt'] = fitted_parameters[4]
            fitted_peaks = fitted_peaks + [peak]
        except:
            # print("Couldn't fit peak candidate: {}".format(peak_candidate))
            pass

    return fitted_peaks


def example_pipeline(show_mesh_plot=False, show_plot_fit=True, silent=True, max_peaks=15):
    if show_plot_fit or show_mesh_plot:
        plt.style.use('dark_background')
        plt.ion()
        plt.show()

    print("Loading data...")
    # raw_data = read_mzxml(
    # '/data/toydata/toy_data.mzXML',
    # instrument_type = 'orbitrap',
    # resolution_ms1 = 70000,
    # resolution_msn = 30000,
    # reference_mz = 200,
    # fwhm_rt = 9,
    # polarity = 'pos',
    # min_mz = 801,
    # max_mz = 803,
    # min_rt = 2808,
    # max_rt = 2928,
    # )
    raw_data = read_mzxml(
        '/data/toydata/toy_data_tof.mzXML',
        # FIXME: This is not correct, should be TOF, but not currently available.
        instrument_type='tof',
        resolution_ms1=30000,
        resolution_msn=30000,
        reference_mz=200,
        fwhm_rt=9,
        polarity='pos',
        min_mz=510,
        max_mz=531,
        min_rt=2390,
        max_rt=2510,
    )

    print("Resampling...")
    mesh = resample(raw_data, 10, 10, 0.5, 0.5)

    print("Saving mesh to disk...")
    mesh.save("mesh.dat")

    # print("Finding local maxima in mesh...")
    local_max = find_local_max(mesh)
    local_max = pd.DataFrame(local_max)
    local_max.columns = ['i', 'j', 'mz', 'rt', 'intensity']
    local_max = local_max.sort_values('intensity', ascending=False)
    if max_peaks != math.inf:
        local_max = local_max[0:max_peaks]

    if show_mesh_plot:
        print("Plotting mesh...")
        mesh_plot = plot_mesh(mesh, transform='sqrt')

        print("Plotting local maxima...")
        mesh_plot['img_plot'].scatter(
            local_max['i'], local_max['j'], color='aqua', s=5, marker="s", alpha=0.9)

    print("Fitting peaks...")
    peak_candidates = find_roi(raw_data, local_max)
    fitted_peaks = []
    if show_plot_fit:
        fig_mz = plt.figure()
        fig_rt = plt.figure()
    for peak_candidate in peak_candidates:
        try:
            # fitted_parameters = fitted_parameters + [fit(raw_data, peak_candidate)]
            # fitted_parameters = fit2(raw_data, peak_candidate)
            fitted_parameters = fit3(raw_data, peak_candidate)
            peak = peak_candidate
            peak['fitted_height'] = fitted_parameters[0]
            peak['fitted_mz'] = fitted_parameters[1]
            peak['fitted_sigma_mz'] = fitted_parameters[2]
            peak['fitted_rt'] = fitted_parameters[3]
            peak['fitted_sigma_rt'] = fitted_parameters[4]
            fitted_peaks = fitted_peaks + [peak]
            if show_plot_fit:
                plot_peak_fit(raw_data, peak, fig_mz, fig_rt)
        except Exception as e:
            print(e)
            pass

    # fitted_peaks = fit_peaks(raw_data, local_max, show_plot_fit=show_plot_fit)
    # fitted_peaks_tuple = [tuple(fitted_peaks.iloc[row]) for row in range(0, fitted_peaks.shape[0])]
    # print("Saving fitted peaks to disk...")
    # tapp.save_fitted_peaks(list(fitted_peaks_tuple), "fitted_peaks.bpks")
    # pd.DataFrame(fitted_peaks).to_csv('fitted_peaks.csv')

    return (raw_data, mesh, local_max, fitted_peaks)


def debugging_qatar():
    file_name = "/data/qatar/17122018/mzXML/Acute2U_3001.mzXML"
    tapp_parameters = {
        'instrument_type': 'orbitrap',
        'resolution_ms1': 70000,
        'resolution_msn': 30000,
        'reference_mz': 200,
        'avg_fwhm_rt': 9,
        'num_samples_mz': 5,
        'num_samples_rt': 5,
        'max_peaks': 1000000,
        # 'max_peaks': 20,
    }
    print("Reading raw data")
    raw_data = tapp.read_mzxml(
        file_name,
        instrument_type=tapp_parameters['instrument_type'],
        resolution_ms1=tapp_parameters['resolution_ms1'],
        resolution_msn=tapp_parameters['resolution_msn'],
        reference_mz=tapp_parameters['reference_mz'],
        # NOTE: For testing purposes
        fwhm_rt=tapp_parameters['avg_fwhm_rt'],
        # min_mz=313.06909,
        # max_mz=313.07223,
        # min_mz=313.05,
        # max_mz=313.08,
        # min_mz=200,
        # max_mz=400,
        min_rt=6.5 * 60,
        max_rt=14 * 60,
        # min_rt=417,
        # max_rt=440,
        polarity='pos',
    )
    print("Resampling")
    mesh = resample(raw_data, 5, 5, 0.5, 0.5)
    plt.style.use('dark_background')
    plt.ion()
    plt.show()
    # plot_mesh(mesh)

    # Testing internal peak finding routine.
    print("Finding peaks")
    peaks = find_peaks(raw_data, mesh)
    peaks_df = pd.DataFrame(
        {
            'local_max_mz': np.array([peak.local_max_mz for peak in peaks]),
            'local_max_rt': np.array([peak.local_max_rt for peak in peaks]),
            'local_max_height': np.array([peak.local_max_height for peak in peaks]),
            'slope_descent_mz': np.array([peak.slope_descent_mz for peak in peaks]),
            'slope_descent_rt': np.array([peak.slope_descent_rt for peak in peaks]),
            'slope_descent_sigma_mz': np.array([peak.slope_descent_sigma_mz for peak in peaks]),
            'slope_descent_sigma_rt': np.array([peak.slope_descent_sigma_rt for peak in peaks]),
            'slope_descent_total_intensity': np.array([peak.slope_descent_total_intensity for peak in peaks]),
            'slope_descent_border_background': np.array([peak.slope_descent_border_background for peak in peaks]),
            'raw_roi_mz': np.array([peak.raw_roi_mean_mz for peak in peaks]),
            'raw_roi_rt': np.array([peak.raw_roi_mean_rt for peak in peaks]),
            'raw_roi_sigma_mz': np.array([peak.raw_roi_sigma_mz for peak in peaks]),
            'raw_roi_sigma_rt': np.array([peak.raw_roi_sigma_rt for peak in peaks]),
            'raw_roi_total_intensity': np.array([peak.raw_roi_total_intensity for peak in peaks]),
            'raw_roi_max_height': np.array([peak.raw_roi_max_height for peak in peaks]),
            'raw_roi_num_points': np.array([peak.raw_roi_num_points for peak in peaks]),
            'raw_roi_num_scans': np.array([peak.raw_roi_num_scans for peak in peaks]),
        })
    peaks_df = peaks_df.loc[(np.array(peaks_df['raw_roi_num_scans']) >= 3),:]

    # print("Fitting peaks via least_squares")
    # fitted_peaks = []
    # for peak_candidate in peaks:
        # fitted_peak = fit_guos_2d_from_peak(peak_candidate)
        # fitted_peaks = fitted_peaks + [fitted_peak]

    # fitted_peaks = pd.DataFrame(fitted_peaks)
    # fitted_peaks.columns = ['fitted_height', 'fitted_mz',
                            # 'fitted_sigma_mz', 'fitted_rt', 'fitted_sigma_rt']
    # peaks_df = pd.concat([peaks_df, fitted_peaks], axis=1)

    print("Plotting ")
    fig = plt.figure()
    plt.subplot(2, 1, 1)
    plt.title('slope_descent')
    plt.scatter(
        peaks_df['local_max_mz'],
        peaks_df['slope_descent_sigma_mz'],
        color='crimson', alpha=0.7, s=3)
    plt.ylim(bottom=0)
    plt.subplot(2, 1, 2)
    plt.title('raw_roi')
    plt.scatter(
        peaks_df['local_max_mz'],
        peaks_df['raw_roi_sigma_mz'],
        color='crimson', alpha=0.7, s=3)
    plt.ylim(bottom=0)
    plt.xlabel('m/z')
    fig = plt.figure()
    plt.subplot(2, 1, 1)
    plt.title('slope_descent')
    plt.scatter(
        peaks_df['slope_descent_rt'],
        peaks_df['slope_descent_sigma_rt'],
        color='crimson', alpha=0.7, s=3)
    plt.ylim(bottom=0)
    plt.subplot(2, 1, 2)
    plt.title('raw_roi')
    plt.scatter(
        peaks_df['raw_roi_rt'],
        peaks_df['raw_roi_sigma_rt'],
        color='crimson', alpha=0.7, s=3)
    plt.ylim(bottom=0)
    plt.xlabel('rt (s)')

    return raw_data, mesh, peaks_df, peaks

def peak_extraction(file_name, tapp_parameters):
    print("Reading raw data")
    raw_data = tapp.read_mzxml(
        file_name,
        min_mz=tapp_parameters['min_mz'],
        max_mz=tapp_parameters['max_mz'],
        min_rt=tapp_parameters['min_rt'],
        max_rt=tapp_parameters['max_rt'],
        instrument_type=tapp_parameters['instrument_type'],
        resolution_ms1=tapp_parameters['resolution_ms1'],
        resolution_msn=tapp_parameters['resolution_msn'],
        reference_mz=tapp_parameters['reference_mz'],
        fwhm_rt=tapp_parameters['avg_fwhm_rt'],
        polarity=tapp_parameters['polarity'],
    )
    print("Resampling")
    mesh = resample(
        raw_data,
        tapp_parameters['num_samples_mz'],
        tapp_parameters['num_samples_rt'],
        tapp_parameters['smoothing_coefficient_mz'],
        tapp_parameters['smoothing_coefficient_rt'],
        )

    print("Finding peaks")
    peaks = find_peaks(raw_data, mesh, tapp_parameters['max_peaks'])
    print("Found {} peaks".format(len(peaks)))

    return raw_data, mesh, peaks

def testing_warping():
    # TODO: Load and peak detect two files
    file_name_a = "/data/qatar/17122018/mzXML/AcutePreU_3001.mzXML"
    file_name_b = "/data/qatar/17122018/mzXML/Acute2U_3002.mzXML"
    tapp_parameters = {
        'instrument_type': 'orbitrap',
        'resolution_ms1': 70000,
        'resolution_msn': 30000,
        'reference_mz': 200,
        'avg_fwhm_rt': 9,
        'num_samples_mz': 5,
        'num_samples_rt': 5,
        'max_peaks': 100,
        'min_mz': 200,
        'max_mz': 400,
        'min_rt': 100,
        'max_rt': 300,
        # 'min_mz': 0,
        # 'max_mz': 2000,
        # 'min_rt': 0,
        # 'max_rt': 2000,
        # 'max_peaks': 20,
    }
    raw_data_a, mesh_a, peaks_df_a, peaks_a = peak_extraction(file_name_a, tapp_parameters, 'pos')
    raw_data_b, mesh_b, peaks_df_b, peaks_b = peak_extraction(file_name_b, tapp_parameters, 'pos')
    unwarped_peaks = [peaks_a, peaks_b]
    print("Warping...")
    warped_peaks = warp_peaks(unwarped_peaks, 0, 50, 50, 2000, 0.2, 100)
    print("Finding similarity...")
    print(tapp.find_similarity(unwarped_peaks[0], unwarped_peaks[1], 10000))
    print(tapp.find_similarity(warped_peaks[0], warped_peaks[1], 10000))
    return unwarped_peaks, warped_peaks


    # FIXME: Debug
    # plt.style.use('dark_background')
    # plt.ion()
    # plt.show()
    # mesh_plot_a = plot_mesh(mesh_a, transform='sqrt')
    # mesh_plot_b = plot_mesh(mesh_b, transform='sqrt')

    # TODO: Warp file_b with file_a as reference
    # TODO: Compare total similarity before and after warping.

def plot_xic(peak, raw_data, figure=None, method="max"):
    x, y = peak.xic(raw_data, method=method)
    plt.style.use('dark_background')
    if not figure:
        figure = plt.figure()

    plt.ion()
    plt.show()
    plt.plot(x, y, label='peak_id = {}'.format(peak.id))
    plt.xlabel('Retention time (s)')
    plt.ylabel('Intensity')
    plt.legend()

    return figure

def testing_xic_plotting(N=20):
    file_name = '/data/toydata/toy_data_tof.mzXML'
    tapp_parameters = {
        'instrument_type': 'tof',
        'resolution_ms1': 30000,
        'resolution_msn': 30000,
        'reference_mz': 200,
        'avg_fwhm_rt': 15,
        'min_mz': 510,
        'max_mz': 531,
        'min_rt': 2390,
        'max_rt': 2510,
    }
    print("Reading raw data")
    raw_data = tapp.read_mzxml(
        file_name,
        instrument_type=tapp_parameters['instrument_type'],
        resolution_ms1=tapp_parameters['resolution_ms1'],
        resolution_msn=tapp_parameters['resolution_msn'],
        reference_mz=tapp_parameters['reference_mz'],
        # NOTE: For testing purposes
        fwhm_rt=tapp_parameters['avg_fwhm_rt'],
        min_mz=tapp_parameters['min_mz'],
        max_mz=tapp_parameters['max_mz'],
        min_rt=tapp_parameters['min_rt'],
        max_rt=tapp_parameters['max_rt'],
    )
    print("Resampling")
    mesh = resample(raw_data, 5, 5, 0.5, 0.5)
    plt.style.use('dark_background')
    plt.ion()
    plt.show()
    plot_mesh(mesh)

    # Testing internal peak finding routine.
    print("Finding peaks")
    peaks = find_peaks(raw_data, mesh)
    # peaks_df = pd.DataFrame(
        # {
            # 'id': np.array([peak.id for peak in peaks]),
            # 'local_max_mz': np.array([peak.local_max_mz for peak in peaks]),
            # 'local_max_rt': np.array([peak.local_max_rt for peak in peaks]),
            # 'local_max_height': np.array([peak.local_max_height for peak in peaks]),
            # 'slope_descent_mz': np.array([peak.slope_descent_mz for peak in peaks]),
            # 'slope_descent_rt': np.array([peak.slope_descent_rt for peak in peaks]),
            # 'slope_descent_sigma_mz': np.array([peak.slope_descent_sigma_mz for peak in peaks]),
            # 'slope_descent_sigma_rt': np.array([peak.slope_descent_sigma_rt for peak in peaks]),
            # 'slope_descent_total_intensity': np.array([peak.slope_descent_total_intensity for peak in peaks]),
            # 'slope_descent_border_background': np.array([peak.slope_descent_border_background for peak in peaks]),
            # 'raw_roi_mz': np.array([peak.raw_roi_mean_mz for peak in peaks]),
            # 'raw_roi_rt': np.array([peak.raw_roi_mean_rt for peak in peaks]),
            # 'raw_roi_sigma_mz': np.array([peak.raw_roi_sigma_mz for peak in peaks]),
            # 'raw_roi_sigma_rt': np.array([peak.raw_roi_sigma_rt for peak in peaks]),
            # 'raw_roi_total_intensity': np.array([peak.raw_roi_total_intensity for peak in peaks]),
            # 'raw_roi_max_height': np.array([peak.raw_roi_max_height for peak in peaks]),
            # 'raw_roi_num_points': np.array([peak.raw_roi_num_points for peak in peaks]),
            # 'raw_roi_num_scans': np.array([peak.raw_roi_num_scans for peak in peaks]),
        # })

    # print("Fitting peaks via least_squares")
    # fitted_peaks = []
    # for peak_candidate in peaks:
        # fitted_peak = fit_guos_2d_from_peak(peak_candidate)
        # fitted_peaks = fitted_peaks + [fitted_peak]

    # fitted_peaks = pd.DataFrame(fitted_peaks)
    # fitted_peaks.columns = ['fitted_height', 'fitted_mz',
                            # 'fitted_sigma_mz', 'fitted_rt', 'fitted_sigma_rt']
    # peaks_df = pd.concat([peaks_df, fitted_peaks], axis=1)

    print("Plotting xic")
    fig = plt.figure()
    for i in range(0, N):
        fig = peaks[i].plot_xic(raw_data, fig)

    return raw_data, mesh, peaks

def fit_sigmas(peak):
    X = np.array(
        [
            [
                peak.a_2_2(),
                peak.a_2_4(),
            ],
            [
                peak.a_4_2(),
                peak.a_4_4(),
            ],
        ],
    )
    Y = np.array([
        peak.c_2(),
        peak.c_4(),
    ])

    print(X, Y)
    beta = np.linalg.lstsq(X, Y, rcond=None)
    beta_2, beta_4 = beta[0]
    var_x = 1/(2 * beta_2)
    var_y = 1/(2 * beta_4)

    print(var_x, var_y)
    if var_x <= 0 or var_y <= 0:
        return np.nan, np.nan

    sigma_mz = np.sqrt(var_x)
    sigma_rt = np.sqrt(var_y)

    return sigma_mz, sigma_rt

def fit_height_and_sigmas(peak):
    X = np.array(
        [
            [
                peak.a_0_0(),
                peak.a_0_2(),
                peak.a_0_4(),
            ],
            [
                peak.a_2_0(),
                peak.a_2_2(),
                peak.a_2_4(),
            ],
            [
                peak.a_4_0(),
                peak.a_4_2(),
                peak.a_4_4(),
            ],
        ],
    )
    Y = np.array([
        peak.c_0(),
        peak.c_2(),
        peak.c_4(),
    ])

    print(X, Y)
    beta = np.linalg.lstsq(X, Y, rcond=None)
    beta_0, beta_2, beta_4 = beta[0]
    var_x = -1/(2 * beta_2)
    var_y = -1/(2 * beta_4)

    print(var_x, var_y)
    # if var_x <= 0 or var_y <= 0:
        # return np.nan, np.nan

    sigma_mz = np.sqrt(var_x)
    sigma_rt = np.sqrt(var_y)
    height = np.exp(beta_0)

    return height, sigma_mz, sigma_rt

def load_toy_data():
    file_name = '/data/toydata/toy_data_tof.mzXML'
    tapp_parameters = {
        'instrument_type': 'tof',
        'resolution_ms1': 30000,
        'resolution_msn': 30000,
        'reference_mz': 200,
        'avg_fwhm_rt': 15,
        'min_mz': 510,
        'max_mz': 531,
        'min_rt': 2390,
        'max_rt': 2510,
    }
    print("Reading raw data")
    raw_data = tapp.read_mzxml(
        file_name,
        instrument_type=tapp_parameters['instrument_type'],
        resolution_ms1=tapp_parameters['resolution_ms1'],
        resolution_msn=tapp_parameters['resolution_msn'],
        reference_mz=tapp_parameters['reference_mz'],
        # NOTE: For testing purposes
        fwhm_rt=tapp_parameters['avg_fwhm_rt'],
        min_mz=tapp_parameters['min_mz'],
        max_mz=tapp_parameters['max_mz'],
        min_rt=tapp_parameters['min_rt'],
        max_rt=tapp_parameters['max_rt'],
    )
    print("Resampling")
    mesh = resample(raw_data, 5, 5, 0.5, 0.5)
    print("Finding peaks")
    peaks = find_peaks(raw_data, mesh)
    return raw_data, mesh, peaks

def load_hye_data_example():
    file_name = '/data/toydata/toy_data_hye.mzXML'
    # file_name = '/data/toydata/toy_data_hye_2.mzXML'
    # file_name = '/data/toydata/toy_data_hye_3.mzXML'
    # file_name = '/data/toydata/toy_data_hye_4.mzXML'
    # file_name = '/data/toydata/toy_data_hye_5.mzXML'
    # file_name = '/data/toydata/toy_data_hye_6.mzXML'
    tapp_parameters = {
        'instrument_type': 'orbitrap',
        'resolution_ms1': 70000,
        'resolution_msn': 30000,
        'reference_mz': 200,
        'avg_fwhm_rt': 30,
        'min_mz': 0,
        'max_mz': 1000,
        'min_rt': 0,
        'max_rt': 10000,
    }
    print("Reading raw data")
    raw_data = tapp.read_mzxml(
        file_name,
        instrument_type=tapp_parameters['instrument_type'],
        resolution_ms1=tapp_parameters['resolution_ms1'],
        resolution_msn=tapp_parameters['resolution_msn'],
        reference_mz=tapp_parameters['reference_mz'],
        # NOTE: For testing purposes
        fwhm_rt=tapp_parameters['avg_fwhm_rt'],
        min_mz=tapp_parameters['min_mz'],
        max_mz=tapp_parameters['max_mz'],
        min_rt=tapp_parameters['min_rt'],
        max_rt=tapp_parameters['max_rt'],
    )
    print("Resampling")
    mesh = resample(raw_data, 10, 10, 0.4, 0.4)
    print("Finding peaks")
    peaks = find_peaks(raw_data, mesh)
    return raw_data, mesh, peaks

def debugging_peak_fitting(fig = None):
    # Load data
    raw_data, mesh, peaks = load_toy_data()
    peak = peaks[0]

    # Setup plotting figures and parameters
    plt.style.use('dark_background')
    plt.ion()
    plt.show()

    if not fig:
        fig = plt.figure()

    data_points = find_raw_points(
        raw_data,
        peak.roi_min_mz,
        peak.roi_max_mz,
        peak.roi_min_rt,
        peak.roi_max_rt,
    )
    rts = data_points.rt
    mzs = data_points.mz
    intensities = data_points.intensity

    np.random.seed(0)

    # Generate random color
    color = np.random.rand(3, 1).flatten()

    plt.figure(fig.number)

    # MZ plot.
    plt.subplot(2, 1, 1)
    sort_idx_mz = np.argsort(mzs)
    markerline, stemlines, baseline = plt.stem(np.array(mzs)[sort_idx_mz], np.array(
        intensities)[sort_idx_mz], label='intensities', markerfmt=' ')
    plt.setp(baseline, color=color, alpha=0.5)
    plt.setp(stemlines, color=color, alpha=0.5)
    # plt.plot(np.array(mzs)[sort_idx_mz], fitted_intensity_2d_mz,
             # linestyle='--', color=color, label='2d_fitting')
    plt.xlabel('m/z')
    plt.ylabel('Intensity')
    plt.xlim(peak.roi_min_mz, peak.roi_max_mz)

    # Raw data plot.
    plt.subplot(2, 1, 2)
    plt.scatter(mzs, rts, c=intensities, label='raw values')
    plt.scatter(
        peak.local_max_mz, peak.local_max_rt,
        color='red',
        alpha=0.8,
        label='smoothed local max',
        )
    plt.xlabel('m/z')
    plt.ylabel('Retention time (s)')
    plt.xlim(peak.roi_min_mz, peak.roi_max_mz)
    plt.legend()

    # height = peak.local_max_height
    # mz = peak.local_max_mz
    # rt = peak.local_max_rt
    # print(data_points.mz)
    # print(data_points.rt)
    # print(data_points.intensity)

def plot_raw_points(peak, raw_data, img_plot=None, rt_plot=None, mz_plot=None, xic_method="max"):
    data_points = find_raw_points(
        raw_data,
        peak.roi_min_mz,
        peak.roi_max_mz,
        peak.roi_min_rt,
        peak.roi_max_rt,
    )
    rts = data_points.rt
    mzs = data_points.mz
    intensities = data_points.intensity

    # Calculate min/max values for the given peak.
    min_mz = peak.roi_min_mz
    max_mz = peak.roi_max_mz
    min_rt = peak.roi_min_rt
    max_rt = peak.roi_max_rt

    if not img_plot and not rt_plot and not mz_plot:
        plt.style.use('dark_background')
        plt.ion()
        plt.show()
        fig = plt.figure()
        plt.clf()
        gs = gridspec.GridSpec(5, 5)
        mz_plot = plt.subplot(gs[0, :-1])
        mz_plot.margins(x=0)
        mz_plot.set_xticks([])
        mz_plot.set_ylabel("Intensity")
        rt_plot = plt.subplot(gs[1:, -1])
        rt_plot.margins(y=0)
        rt_plot.set_yticks([])
        rt_plot.set_xlabel("Intensity")
        img_plot = plt.subplot(gs[1:, :-1])

        # Set the min/max limits for mz/rt.
        mz_plot.set_xlim([min_mz, max_mz])
        rt_plot.set_ylim([min_rt, max_rt])
        img_plot.set_xlim([min_mz, max_mz])
        img_plot.set_ylim([min_rt, max_rt])


    # NOTE: Adding 200 for a more pleasant color map on the first peaks, found this
    # number by trial and error, dont @ me.
    np.random.seed(peak.id + 200)
    color = np.append(np.random.rand(3,1).flatten(), 0.5)
    np.random.seed(None)

    if img_plot:
        img_plot.scatter(
            mzs, rts,
            c=np.sqrt(intensities),
            edgecolor=color,
            )
    if rt_plot:
        x, y = peak.xic(raw_data, method=xic_method)
        rt_plot.plot(y, x, color=color)
    if mz_plot:
        sort_idx_mz = np.argsort(mzs)
        markerline, stemlines, baseline = mz_plot.stem(
            np.array(mzs)[sort_idx_mz],
            np.array(intensities)[sort_idx_mz],
            markerfmt=' ',
            )
        plt.setp(baseline, color=color, alpha=0.5)
        plt.setp(stemlines, color=color, alpha=0.5)

    # Set x/y limits if necessary.
    lim_min_mz, lim_max_mz = img_plot.get_xlim()
    lim_min_rt, lim_max_rt = img_plot.get_ylim()
    if min_mz < lim_min_mz:
        lim_min_mz = min_mz
    if min_rt < lim_min_rt:
        lim_min_rt = min_rt
    if max_mz > lim_max_mz:
        lim_max_mz = max_mz
    if max_rt > lim_max_rt:
        lim_max_rt = max_rt
    mz_plot.set_xlim([lim_min_mz, lim_max_mz])
    rt_plot.set_ylim([lim_min_rt, lim_max_rt])
    img_plot.set_xlim([lim_min_mz, lim_max_mz])
    img_plot.set_ylim([lim_min_rt, lim_max_rt])

    return({
        "img_plot": img_plot,
        "mz_plot": mz_plot,
        "rt_plot": rt_plot,
    })

def plot_sigma(
        peak,
        height, mz, rt,
        sigma_mz, sigma_rt,
        img_plot=None, rt_plot=None, mz_plot=None,
        linestyle='--',
        label=None,
        marker='.',
        ):
    # Calculate min/max values for the given peak.
    min_mz = mz - 3 * sigma_mz
    max_mz = mz + 3 * sigma_mz
    min_rt = rt - 3 * sigma_rt
    max_rt = rt + 3 * sigma_rt

    if not img_plot and not rt_plot and not mz_plot:
        plt.style.use('dark_background')
        plt.ion()
        plt.show()
        fig = plt.figure()
        plt.clf()
        gs = gridspec.GridSpec(5, 5)
        mz_plot = plt.subplot(gs[0, :-1])
        mz_plot.margins(x=0)
        mz_plot.set_xticks([])
        mz_plot.set_ylabel("Intensity")
        rt_plot = plt.subplot(gs[1:, -1])
        rt_plot.margins(y=0)
        rt_plot.set_yticks([])
        rt_plot.set_xlabel("Intensity")
        img_plot = plt.subplot(gs[1:, :-1])

        # Set the min/max limits for mz/rt.
        mz_plot.set_xlim([min_mz, max_mz])
        rt_plot.set_ylim([min_rt, max_rt])
        img_plot.set_xlim([min_mz, max_mz])
        img_plot.set_ylim([min_rt, max_rt])

    # NOTE: Adding 200 for a more pleasant color map on the first peaks, found this
    # number by trial and error, dont @ me.
    np.random.seed(peak.id + 200)
    base_color = np.random.rand(3,1).flatten()
    np.random.seed(None)

    lim_min_mz, lim_max_mz = img_plot.get_xlim()
    lim_min_rt, lim_max_rt = img_plot.get_ylim()
    if img_plot:
        # Set the limits for the img_plot
        if min_mz < lim_min_mz:
            lim_min_mz = min_mz
        if min_rt < lim_min_rt:
            lim_min_rt = min_rt
        if max_mz > lim_max_mz:
            lim_max_mz = max_mz
        if max_rt > lim_max_rt:
            lim_max_rt = max_rt
        img_plot.set_xlim([lim_min_mz, lim_max_mz])
        img_plot.set_ylim([lim_min_rt, lim_max_rt])

        # Plotting the center of the peak.
        color_0 = np.append(base_color, 1)
        img_plot.scatter(
            mz, rt,
            marker=marker,
            label=label,
            color=color_0, facecolors='none', edgecolors=color_0,
            )

        color_1 = np.append(base_color, 0.9)
        elip_1 = Ellipse(
        (mz, rt),
        2 * sigma_mz,
        2 * sigma_rt,
        fill=False,
        color=color_1,
        linestyle=linestyle,
        )
        color_2 = np.append(base_color, 0.6)
        elip_2 = Ellipse(
        (mz, rt),
        2 * 2 * sigma_mz,
        2 * 2 * sigma_rt,
        fill=False,
        color=color_2,
        linestyle=linestyle,
        )
        color_3 = np.append(base_color, 0.4)
        elip_3 = Ellipse(
        (mz, rt),
        3 * 2 * sigma_mz,
        3 * 2 * sigma_rt,
        fill=False,
        color=color_3,
        linestyle=linestyle,
        )
        img_plot.add_artist(elip_1)
        img_plot.add_artist(elip_2)
        img_plot.add_artist(elip_3)
    if rt_plot:
        # Set the limits for mz_plot.
        if min_rt < lim_min_rt:
            lim_min_rt = min_rt
        if max_rt > lim_max_rt:
            lim_max_rt = max_rt
        img_plot.set_xlim([lim_min_mz, lim_max_mz])
        img_plot.set_ylim([lim_min_rt, lim_max_rt])
        rt_plot.set_ylim([lim_min_rt, lim_max_rt])
        x = np.linspace(min_rt, max_rt, 100)
        y = gaus(x, height, rt, sigma_rt)
        rt_plot.plot(
            y, x,
            linestyle=linestyle,
            color=base_color,
            label=label,
            )
    if mz_plot:
        # Set the limits for rt_plot.
        if min_mz < lim_min_mz:
            lim_min_mz = min_mz
        if max_mz > lim_max_mz:
            lim_max_mz = max_mz
        mz_plot.set_xlim([lim_min_mz, lim_max_mz])
        x = np.linspace(min_mz, max_mz, 100)
        y = gaus(x, height, mz, sigma_mz)
        mz_plot.plot(
            x, y,
            linestyle=linestyle, 
            color=base_color,
            label=label,
            )

    return({
        "img_plot": img_plot,
        "mz_plot": mz_plot,
        "rt_plot": rt_plot,
    })

def plot_raw_roi_sigma(peak, img_plot=None, rt_plot=None, mz_plot=None):
    return plot_sigma(
        peak,
        peak.local_max_height,
        peak.local_max_mz,
        peak.local_max_rt,
        peak.raw_roi_sigma_mz,
        peak.raw_roi_sigma_rt,
        img_plot,
        rt_plot,
        mz_plot,
        label='raw_roi',
        marker='s',
        )

def plot_raw_roi_fitted_sigma(peak, raw_data, img_plot=None, rt_plot=None, mz_plot=None):
    data_points = find_raw_points(
        raw_data,
        peak.roi_min_mz,
        peak.roi_max_mz,
        peak.roi_min_rt,
        peak.roi_max_rt
    )
    mzs = np.array(data_points.mz)
    rts = np.array(data_points.rt)
    intensities = np.array(data_points.intensity)
    X = np.array([mzs, rts])
    f = lambda x, h, mz, sigma_mz, rt, sigma_rt: gaus2d(x, h, peak.local_max_mz, sigma_mz, peak.local_max_rt, sigma_rt)
    fitted_parameters, pcov_2d = curve_fit(f, X, intensities, p0=[
        peak.raw_roi_max_height, peak.local_max_mz, peak.raw_roi_sigma_mz, peak.local_max_rt, peak.raw_roi_sigma_rt])

    fitted_height, fitted_mz, fitted_sigma_mz, fitted_rt, fitted_sigma_rt = fitted_parameters

    return plot_sigma(
        peak,
        fitted_height,
        fitted_mz,
        fitted_rt,
        fitted_sigma_mz,
        fitted_sigma_rt,
        img_plot,
        rt_plot,
        mz_plot,
        linestyle='-',
        label='fitted_raw_roi',
        marker='.',
        )

def plot_raw_roi_fitted_sigma_fast(peak, raw_data, img_plot=None, rt_plot=None, mz_plot=None):
    data_points = find_raw_points(
        raw_data,
        peak.roi_min_mz,
        peak.roi_max_mz,
        peak.roi_min_rt,
        peak.roi_max_rt
    )
    mzs = np.array(data_points.mz)
    rts = np.array(data_points.rt)
    intensities = np.array(data_points.intensity)
    fitted_parameters = fit_guos_2d(mzs, rts, intensities)

    fitted_height, fitted_mz, fitted_sigma_mz, fitted_rt, fitted_sigma_rt = fitted_parameters

    return plot_sigma(
        peak,
        fitted_height,
        fitted_mz,
        fitted_rt,
        fitted_sigma_mz,
        fitted_sigma_rt,
        img_plot,
        rt_plot,
        mz_plot,
        linestyle=':',
        label='fitted_raw_roi (fast)',
        marker='P',
        )

def plot_raw_roi_fitted_sigma_weighted(peak, raw_data, img_plot=None, rt_plot=None, mz_plot=None):
    data_points = find_raw_points(
        raw_data,
        peak.roi_min_mz,
        peak.roi_max_mz,
        peak.roi_min_rt,
        peak.roi_max_rt
    )
    mzs = np.array(data_points.mz)
    rts = np.array(data_points.rt)
    intensities = np.array(data_points.intensity)
    fwhm_mz = raw_data.theoretical_fwhm(peak.local_max_mz)
    theoretical_sigma_rt = raw_data.fwhm_rt/(2 * np.sqrt(2 * np.log(2)))
    theoretical_sigma_mz = fwhm_mz/(2 * np.sqrt(2 * np.log(2)))
    # IMPORTANT: Since multiple peaks might appear within the 3 * sigma ROI of
    # a peak, the R2 calculated from this number can be skewed. For this reason,
    # we are only using +-1 * sigma for the estimation of R2.
    min_mz = peak.local_max_mz - theoretical_sigma_mz
    max_mz = peak.local_max_mz + theoretical_sigma_mz
    min_rt = peak.local_max_rt - theoretical_sigma_rt
    max_rt = peak.local_max_rt + theoretical_sigma_rt
    idx = (mzs > min_mz) & (mzs < max_mz) & (rts > min_rt) & (rts < max_rt)
    mzs = np.copy(mzs[idx])
    rts = np.copy(rts[idx])
    intensities = np.copy(intensities[idx])
    # fitted_parameters = fit_weighted_guos_2d_constrained(mzs, rts, intensities, peak.local_max_mz, peak.local_max_rt, theoretical_sigma_mz, theoretical_sigma_rt)
    fitted_parameters = fit_weighted_guos_2d(mzs, rts, intensities, peak.local_max_mz, peak.local_max_rt, theoretical_sigma_mz, theoretical_sigma_rt)

    fitted_height, fitted_mz, fitted_sigma_mz, fitted_rt, fitted_sigma_rt = fitted_parameters

    return plot_sigma(
        peak,
        fitted_height,
        fitted_mz,
        fitted_rt,
        fitted_sigma_mz,
        fitted_sigma_rt,
        img_plot,
        rt_plot,
        mz_plot,
        linestyle='-',
        label='fitted_raw_roi (weighted)',
        marker='P',
        )

def plot_theoretical_sigma(peak, raw_data, img_plot=None, rt_plot=None, mz_plot=None):
    fwhm_mz = raw_data.theoretical_fwhm(peak.local_max_mz)
    theoretical_sigma_rt = raw_data.fwhm_rt/(2 * np.sqrt(2 * np.log(2)))
    theoretical_sigma_mz = fwhm_mz/(2 * np.sqrt(2 * np.log(2)))
    return plot_sigma(
        peak,
        peak.local_max_height,
        peak.local_max_mz,
        peak.local_max_rt,
        theoretical_sigma_mz,
        theoretical_sigma_rt,
        img_plot,
        rt_plot,
        mz_plot,
        linestyle=':',
        label='fitted_raw_roi (fast)',
        marker='P',
        )

def plot_slope_descent_sigma(peak, img_plot=None, rt_plot=None, mz_plot=None):
    return plot_sigma(
        peak,
        peak.local_max_height,
        peak.local_max_mz,
        peak.local_max_rt,
        peak.slope_descent_sigma_mz,
        peak.slope_descent_sigma_rt,
        img_plot,
        rt_plot,
        mz_plot,
        linestyle='-',
        label='slope_descent',
        marker='.',
        )

def testing_different_sigmas(peaks, raw_data):
    plots = peaks[0].plot_raw_points(raw_data)
    plots = peaks[0].plot_raw_roi_sigma(plots['img_plot'], plots['rt_plot'], plots['mz_plot'])
    plots = peaks[0].plot_theoretical_sigma(raw_data, plots['img_plot'], plots['rt_plot'], plots['mz_plot'])
    plots = peaks[0].plot_raw_roi_fitted_sigma_weighted(raw_data, plots['img_plot'], plots['rt_plot'], plots['mz_plot'])
    plt.legend()
    return plots

from scipy.special import erf, erfc
def emg(t, h, tg, sigma, tau):
    a = 1/(2 * tau)
    b = 1/2 * np.power(sigma/tau, 2) - (t - tg)/tau
    z = 1 / np.sqrt(2) * ((t - tg)/sigma - sigma/tau)
    c = erfc(-z)
    return h * a * np.exp(b) * c

def gauss_mz_emg_rt(X, h, mz_0, sigma_mz, rt_0, sigma_rt, tau):
    mz = X[0]
    rt = X[1]
    a = 1/(2 * tau)
    b = 1/2 * np.power(sigma_rt/tau, 2) - (rt - rt_0)/tau
    z = 1 / np.sqrt(2) * ((rt - rt_0)/sigma_rt - sigma_rt/tau)
    c = erfc(-z)
    d = np.exp(-0.5 * np.power((mz - mz_0) / sigma_mz, 2))
    return h * a * np.exp(b) * c * d 

def calculate_r2(x, y, z, h, mz, sigma_mz, rt, sigma_rt):
    x = np.array(x)
    y = np.array(y)
    z = np.array(z)
    ss_tot = (np.power(z - z.mean(), 2)).sum()
    ss_res = (np.power(z - gaus2d([x,y], h, mz, sigma_mz, rt, sigma_rt), 2)).sum()
    r2 = 1 - ss_res / ss_tot
    return r2

def fit_and_evaluate_r2(peak, raw_data, verbose = True):
    data_points = find_raw_points(
        raw_data,
        peak.roi_min_mz,
        peak.roi_max_mz,
        peak.roi_min_rt,
        peak.roi_max_rt
    )
    mzs = np.array(data_points.mz)
    rts = np.array(data_points.rt)
    intensities = np.array(data_points.intensity)
    fwhm_mz = raw_data.theoretical_fwhm(peak.local_max_mz)
    theoretical_sigma_rt = raw_data.fwhm_rt/(2 * np.sqrt(2 * np.log(2)))
    theoretical_sigma_mz = fwhm_mz/(2 * np.sqrt(2 * np.log(2)))

    # IMPORTANT: Since multiple peaks might appear within the 3 * sigma ROI of
    # a peak, the R2 calculated from this number can be skewed. For this reason,
    # we are only using +-1 * sigma for the estimation of R2.
    min_mz = peak.local_max_mz - theoretical_sigma_mz
    max_mz = peak.local_max_mz + theoretical_sigma_mz
    min_rt = peak.local_max_rt - theoretical_sigma_rt
    max_rt = peak.local_max_rt + theoretical_sigma_rt
    idx = (mzs > min_mz) & (mzs < max_mz) & (rts > min_rt) & (rts < max_rt)
    mzs = np.copy(mzs[idx])
    rts = np.copy(rts[idx])
    intensities = np.copy(intensities[idx])
    if idx.sum() == 0:
        print(peak.id)

    # Fit 0: Theoretical.
    theoretical_r2 = calculate_r2(
            mzs, rts, intensities,
            peak.local_max_height,
            peak.local_max_mz,
            theoretical_sigma_mz,
            peak.local_max_rt,
            theoretical_sigma_rt,
        )
    if verbose:
        print(
            "[id = {0}][Theoretical]: mz = {1}, rt = {2}, height = {3}, sigma_mz = {4}, sigma_rt = {5}, r2 = {6}".format(
                    peak.id,
                    peak.local_max_mz,
                    peak.local_max_rt,
                    peak.local_max_height, 
                    theoretical_sigma_mz, 
                    theoretical_sigma_rt, 
                    theoretical_r2,
                )
            )
    # Fit 1: Estimated.
    estimated_r2 = calculate_r2(
            mzs, rts, intensities,
            peak.local_max_height,
            peak.local_max_mz,
            peak.raw_roi_sigma_mz,
            peak.local_max_rt,
            peak.raw_roi_sigma_rt,
        )
    if verbose:
        print(
            "[id = {0}][Estimated]: mz = {1}, rt = {2}, height = {3}, sigma_mz = {4}, sigma_rt = {5}, r2 = {6}".format(
                    peak.id,
                    peak.local_max_mz,
                    peak.local_max_rt,
                    peak.local_max_height, 
                    peak.raw_roi_sigma_mz, 
                    peak.raw_roi_sigma_rt, 
                    estimated_r2,
                )
            )
    # Fit 2: Weighted Least Square Fitting.
    fitted_parameters = fit_weighted_guos_2d_constrained(mzs, rts, intensities, peak.local_max_mz, peak.local_max_rt, theoretical_sigma_mz, theoretical_sigma_rt)
    fitted_height, fitted_mz, fitted_sigma_mz, fitted_rt, fitted_sigma_rt = fitted_parameters
    fitted_r2 = calculate_r2(
            mzs, rts, intensities,
            fitted_height,
            fitted_mz,
            fitted_sigma_mz,
            fitted_rt,
            fitted_sigma_rt,
        )
    if verbose:
        print(
            "[id = {0}][Fitted(WeightedLE)]: mz = {1}, rt = {2}, height = {3}, sigma_mz = {4}, sigma_rt = {5}, r2 = {6}".format(
                    peak.id,
                    fitted_mz,
                    fitted_rt,
                    fitted_height, 
                    fitted_sigma_mz, 
                    fitted_sigma_rt, 
                    fitted_r2,
                )
            )
    return (peak.id, theoretical_r2, estimated_r2, fitted_r2)

def calculate_r2_all_peaks(peaks, raw_data, plot_density):
    r2_values = [fit_and_evaluate_r2(peak, raw_data, verbose = False) for peak in peaks]
    r2_values = pd.DataFrame(r2_values, columns=['id', 'theoretical_r2', 'estimated_r2', 'fitted_r2'])
    if plot_density:
        import seaborn as sns
        plt.style.use('dark_background')
        plt.ion()
        plt.show()
        fig = plt.figure()
        sns.distplot(r2_values['theoretical_r2'].dropna(), hist=False, label='theoretical_r2')
        sns.distplot(r2_values['estimated_r2'].dropna(), hist=False, label='estimated_r2')
        sns.distplot(r2_values['fitted_r2'].dropna(), hist=False, label='fitted_r2')
    return r2_values

def to_table(peaks):
    peaks_df = pd.DataFrame(
        {
            'id': np.array([peak.id for peak in peaks]),
            'local_max_mz': np.array([peak.local_max_mz for peak in peaks]),
            'local_max_rt': np.array([peak.local_max_rt for peak in peaks]),
            'local_max_height': np.array([peak.local_max_height for peak in peaks]),
            'slope_descent_mean_mz': np.array([peak.slope_descent_mean_mz for peak in peaks]),
            'slope_descent_mean_rt': np.array([peak.slope_descent_mean_rt for peak in peaks]),
            'slope_descent_sigma_mz': np.array([peak.slope_descent_sigma_mz for peak in peaks]),
            'slope_descent_sigma_rt': np.array([peak.slope_descent_sigma_rt for peak in peaks]),
            'slope_descent_total_intensity': np.array([peak.slope_descent_total_intensity for peak in peaks]),
            'slope_descent_border_background': np.array([peak.slope_descent_border_background for peak in peaks]),
            'raw_roi_mean_mz': np.array([peak.raw_roi_mean_mz for peak in peaks]),
            'raw_roi_mean_rt': np.array([peak.raw_roi_mean_rt for peak in peaks]),
            'raw_roi_sigma_mz': np.array([peak.raw_roi_sigma_mz for peak in peaks]),
            'raw_roi_sigma_rt': np.array([peak.raw_roi_sigma_rt for peak in peaks]),
            'raw_roi_skewness_mz': np.array([peak.raw_roi_skewness_mz for peak in peaks]),
            'raw_roi_skewness_rt': np.array([peak.raw_roi_skewness_rt for peak in peaks]),
            'raw_roi_kurtosis_mz': np.array([peak.raw_roi_kurtosis_mz for peak in peaks]),
            'raw_roi_kurtosis_rt': np.array([peak.raw_roi_kurtosis_rt for peak in peaks]),
            'raw_roi_max_height': np.array([peak.raw_roi_max_height for peak in peaks]),
            'raw_roi_total_intensity': np.array([peak.raw_roi_total_intensity for peak in peaks]),
            'raw_roi_num_points': np.array([peak.raw_roi_num_points for peak in peaks]),
            'raw_roi_num_scans': np.array([peak.raw_roi_num_scans for peak in peaks]),
        })
    return peaks_df


def linked_peptides_to_table(linked_peptides):
    linked_peptides_df = pd.DataFrame(
        {
            'sequence': np.array([linked_peptide.sequence for linked_peptide in linked_peptides]),
            'charge_state': np.array([linked_peptide.charge_state for linked_peptide in linked_peptides]),
            'ident_rt': np.array([linked_peptide.ident_rt for linked_peptide in linked_peptides]),
            'ident_mz': np.array([linked_peptide.ident_mz for linked_peptide in linked_peptides]),
            'number_of_isotopes': np.array([len(linked_peptide.linked_isotopes) for linked_peptide in linked_peptides]),
            'monoisotopic_height': np.array([linked_peptide.monoisotopic_height for linked_peptide in linked_peptides]),
            'monoisotopic_intensity': np.array([linked_peptide.monoisotopic_intensity for linked_peptide in linked_peptides]),
            'total_height': np.array([linked_peptide.total_height for linked_peptide in linked_peptides]),
            'total_intensity': np.array([linked_peptide.total_intensity for linked_peptide in linked_peptides]),
            'weighted_error': np.array([linked_peptide.weighted_error for linked_peptide in linked_peptides]),
            'psm_id': np.array([linked_peptide.psm_id for linked_peptide in linked_peptides]),
        })
    return linked_peptides_df

def create_psm_protein_graph(ident_data):
    unique_proteins = pd.Series(
        [
            protein_hypothesis.db_sequence_id
            for protein_hypothesis in ident_data.protein_hypotheses
        ]).unique()
    unique_psm = np.unique(np.concatenate(
        [
            protein_hypothesis.spectrum_ids
            for protein_hypothesis in ident_data.protein_hypotheses
        ]))
    incidence_matrix = np.zeros([len(unique_psm), len(unique_proteins)])
    for protein_hypothesis in ident_data.protein_hypotheses:
        db_sequence = protein_hypothesis.db_sequence_id
        i = np.where(unique_proteins == db_sequence)[0][0]
        for spectrum_id in protein_hypothesis.spectrum_ids:
            j = np.where(unique_psm == spectrum_id)[0][0]
            incidence_matrix[j, i] = 1
    return (unique_proteins, unique_psm, incidence_matrix)

def razor_proteins(unique_proteins, unique_psm, incidence_matrix):
    # Resolve shared peptides by the Occam's Razor approach.
    # 1.- Sort proteins by number of associated PSM (Descendent).
    number_of_psm_per_protein = incidence_matrix.sum(axis=0)
    sort_index = np.argsort(number_of_psm_per_protein)[::-1]
    unique_proteins = unique_proteins[sort_index]
    incidence_matrix = incidence_matrix[:, sort_index]
    for i in range(0,len(unique_proteins) - 1):
        # FIXME: If we were to be correct, we should reorder the matrix after each
        # iteration. This is computationally very expensive for this prototype
        # function. A better approach should be used for the C++ version.

        # 2.- Greedyly assign PSMs to the first protein they occur and remove PSM from the
        # incidence matrix for the rest of proteins.
        incidence_matrix[np.where(incidence_matrix[:,i] == 1)[0], (i + 1):] = 0

    return (unique_proteins, unique_psm, incidence_matrix)

def psm_db_sequences(ident_data):
    unique_proteins, unique_psm, incidence_matrix = create_psm_protein_graph(ident_data)
    unique_proteins, unique_psm, incidence_matrix = razor_proteins(
        unique_proteins, unique_psm, incidence_matrix)
    db_sequences = [] 
    for psm in ident_data.spectrum_ids: 
        unique_psm_index = np.where(psm.id == unique_psm)[0] 
        if len(unique_psm_index) == 0: 
            db_sequences += [""] 
        else: 
            unique_psm_index = unique_psm_index[0] 
            db_sequence_id = unique_proteins[incidence_matrix[unique_psm_index,:] == 1][0] 
            db_sequences += [db_sequence_id] 
    db_sequences_df = pd.DataFrame(
        {
            "protein_id": [db_sequence.id for db_sequence in ident_data.db_sequences],
            "protein_name": [db_sequence.value for db_sequence in ident_data.db_sequences],
        })
    db_sequences = pd.DataFrame({"protein_id" : db_sequences})
    db_sequences_df = pd.merge(db_sequences, db_sequences_df, how='left')
    db_sequences_df['psm_id'] = [psm.id for psm in ident_data.spectrum_ids]

    return db_sequences_df

def default_parameters(instrument, avg_fwhm_rt):
    if instrument == 'orbitrap':
        tapp_parameters = {
            'instrument_type': 'orbitrap',
            'resolution_ms1': 70000,
            'resolution_msn': 30000,
            'reference_mz': 200,
            'avg_fwhm_rt': avg_fwhm_rt,
            # Meshing.
            'num_samples_mz': 5,
            'num_samples_rt': 5,
            'smoothing_coefficient_mz': 0.4,
            'smoothing_coefficient_rt': 0.4,
            # Warp2D.
            'warp2d_slack': 30,
            'warp2d_window_size': 50,
            'warp2d_num_points': 2000,
            'warp2d_rt_expand_factor': 0.2,
            'warp2d_peaks_per_window': 100,
            # MetaMatch.
            'metamatch_radius_mz': 0.005,
            'metamatch_radius_rt': avg_fwhm_rt,
            'metamatch_fraction': 0.7,
            'max_peaks': 100000,
            'polarity': 'both',
            'min_mz': 0,
            'max_mz': 100000,
            'min_rt': 0,
            'max_rt': 100000,
            # Quality.
            'similarity_num_peaks': 2000,
        }
        return tapp_parameters

# TODO: Should be possible to only run certain steps if the output files already
# exist, loading the data instead.
def dda_pipeline(tapp_parameters, input_files, output_dir = "TAPP", override_existing = False):
    # TODO: Sanitize parameters.
    # TODO: Sanitize input/outputs.
    # TODO:     - Check if file names exist.
    # TODO:     - Check if there are name conflicts.
    # TODO:     - Check that input extension is valid.
    # TODO:     - Check if we have permission to write on output directory.
    # Create lists of files, and groups.
    input_raw_files = []
    input_stems = []
    input_ident_files = []
    groups = []
    for key in sorted(input_files.keys()):
        input_raw_files += [key]
        base_name = os.path.basename(key)
        base_name = os.path.splitext(base_name)
        extension = base_name[1]
        stem = base_name[0]
        input_stems += [stem]
        # TODO:     - Check that all files contain a group, if not, assign a default group distinct from the rest.
        groups += [input_files[key]['group']]
        # TODO:     - Check that all files contain a ident_path, if not, assign 'none'.
        input_ident_files += [input_files[key]['ident_path']]

    # Create output directory and subdirectoreis if necessary.
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists(os.path.join(output_dir, 'raw')):
        os.makedirs(os.path.join(output_dir, 'raw'))
    if not os.path.exists(os.path.join(output_dir, 'quality')):
        os.makedirs(os.path.join(output_dir, 'quality'))
    if not os.path.exists(os.path.join(output_dir, 'mesh')):
        os.makedirs(os.path.join(output_dir, 'mesh'))
    if not os.path.exists(os.path.join(output_dir, 'peaks')):
        os.makedirs(os.path.join(output_dir, 'peaks'))
    if not os.path.exists(os.path.join(output_dir, 'warped_peaks')):
        os.makedirs(os.path.join(output_dir, 'warped_peaks'))
    if not os.path.exists(os.path.join(output_dir, 'metamatch')):
        os.makedirs(os.path.join(output_dir, 'metamatch'))
    if not os.path.exists(os.path.join(output_dir, 'linking')):
        os.makedirs(os.path.join(output_dir, 'linking'))
    if not os.path.exists(os.path.join(output_dir, 'ident')):
        os.makedirs(os.path.join(output_dir, 'ident'))
    if not os.path.exists(os.path.join(output_dir, 'features')):
        os.makedirs(os.path.join(output_dir, 'features'))
    if not os.path.exists(os.path.join(output_dir, 'quant')):
        os.makedirs(os.path.join(output_dir, 'quant'))

    # TODO: Initialize summary, log and parameters files.

    # Raw data to binary conversion.
    for i, file_name in enumerate(input_raw_files):
        # Check if file has already been processed.
        stem = input_stems[i]
        out_path = os.path.join(output_dir, 'raw', "{}.ms1".format(stem))
        if os.path.exists(out_path) and not override_existing:
            continue

        # Read raw files (MS1).
        print('Reading MS1:', file_name)
        raw_data = tapp.read_mzxml(
            file_name,
            min_mz=tapp_parameters['min_mz'],
            max_mz=tapp_parameters['max_mz'],
            min_rt=tapp_parameters['min_rt'],
            max_rt=tapp_parameters['max_rt'],
            instrument_type=tapp_parameters['instrument_type'],
            resolution_ms1=tapp_parameters['resolution_ms1'],
            resolution_msn=tapp_parameters['resolution_msn'],
            reference_mz=tapp_parameters['reference_mz'],
            fwhm_rt=tapp_parameters['avg_fwhm_rt'],
            polarity=tapp_parameters['polarity'],
        )

        # Write raw_data to disk (MS1).
        print('Writing raw MS1:', stem, '({})'.format(out_path))
        raw_data.dump(out_path)

        # TODO: Read raw files (MS2).
        # TODO: Write raw_data to disk (MS2).

    # Perform resampling/smoothing and save results to disk.
    for stem in input_stems:
        # Check if file has already been processed.
        in_path = os.path.join(output_dir, 'raw', "{}.ms1".format(stem))
        out_path = os.path.join(output_dir, 'mesh', "{}.mesh".format(stem))
        if os.path.exists(out_path) and not override_existing:
            continue
        raw_data = tapp.read_raw_data(in_path)
        print("Resampling:", stem)
        mesh = resample(
            raw_data,
            tapp_parameters['num_samples_mz'],
            tapp_parameters['num_samples_rt'],
            tapp_parameters['smoothing_coefficient_mz'],
            tapp_parameters['smoothing_coefficient_rt'],
            )
        print('Writing mesh:', stem, '({})'.format(out_path))
        mesh.dump(out_path)

    # Perform peak detection and save results to disk.
    for stem in input_stems:
        # Check if file has already been processed.
        in_path_raw = os.path.join(output_dir, 'raw', "{}.ms1".format(stem))
        in_path_mesh = os.path.join(output_dir, 'mesh', "{}.mesh".format(stem))
        out_path = os.path.join(output_dir, 'peaks', "{}.bpks".format(stem))
        if os.path.exists(out_path) and not override_existing:
            continue
        raw_data = tapp.read_raw_data(in_path_raw)
        mesh = tapp.read_mesh(in_path_mesh)
        print("Finding peaks:", stem)
        peaks = find_peaks(raw_data, mesh, tapp_parameters['max_peaks'])
        print('Writing peaks:', stem, '({})'.format(out_path))
        tapp.write_peaks(peaks, out_path)

    # Calculate similarity matrix before alignment, generate heatmap and save to disk.
    # TODO: Sort by group and stem name before similarity calculation.
    print("Calculating unwarped similarity matrix.")
    similarity_matrix = np.zeros(len(input_stems) ** 2).reshape(len(input_stems), len(input_stems))
    for i in range(0,len(input_stems)):
        stem_a = input_stems[i]
        peaks_a = tapp.read_peaks(os.path.join(output_dir, 'peaks', '{}.bpks'.format(stem_a)))
        for j in range(i,len(input_stems)):
            stem_b = input_stems[j]
            peaks_b = tapp.read_peaks(os.path.join(output_dir, 'peaks', '{}.bpks'.format(stem_b)))
            similarity_matrix[j,i] = tapp.find_similarity(peaks_a, peaks_b, tapp_parameters['similarity_num_peaks']).geometric_ratio
            similarity_matrix[i,j] = similarity_matrix[j,i]
    # TODO: Proper sorted names? Maybe group row/col colors?
    # similarity_matrix_names = [file_name.split('.')[0] for file_name in file_names]
    similarity_matrix_df = pd.DataFrame(similarity_matrix)
    # similarity_matrix_df.columns = similarity_matrix_names
    # similarity_matrix_df.rename(index=dict(zip(range(0,len(similarity_matrix_names),1), similarity_matrix_names)), inplace=True)
    plt.ion() # TODO: plt.ioff()
    plt.figure()
    import seaborn as sns
    sns.heatmap(similarity_matrix_df, xticklabels=True, yticklabels=True, square=True, vmin=0, vmax=1)
    # TODO: Save figure to disk.

    # TODO: Correct retention time. If a reference sample is selected it will be used, otherwise, exhaustive warping will be performed.
    # TODO: Calculate similarity matrix after alignment, generate heatmap and save to disk.
    # TODO: Use metamatch to match warped peaks.
    return metaclusters
    # TODO: Match ms2 events with corresponding detected peaks.
    # TODO: (If there is ident information)
    # TODO:     - Read mzidentdata and save binaries to disk.
    # TODO:     - Link ms2 events with ident information.
    # TODO:     - Perform Occam's razor protein inference in linked peptides.
    # TODO: Perform feature detection using averagine or linked identification if available in ms2 linked peaks.
    # TODO: Link metamatch clusters and corresponding peaks with identification information of peptides and proteins.
    # TODO: Use maximum likelihood to resolve conflicts among replicates and generate peptide/protein quantitative tables.
    return

def full_dda_pipeline_test():
    input_files = {
            '/data/HYE_DDA_Orbitrap/mzXML/subset/1_1.mzXML': {'group': 1, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/1_2.mzXML': {'group': 1, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/1_3.mzXML': {'group': 1, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/1_4.mzXML': {'group': 1, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/1_5.mzXML': {'group': 1, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/3_1.mzXML': {'group': 3, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/3_2.mzXML': {'group': 3, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/3_3.mzXML': {'group': 3, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/3_4.mzXML': {'group': 3, 'ident_path': 'none'},
            '/data/HYE_DDA_Orbitrap/mzXML/subset/3_5.mzXML': {'group': 3, 'ident_path': 'none'},
        }
    tapp_parameters = default_parameters('orbitrap', 9)
    tapp_parameters['max_peaks'] = 1000
    tapp_parameters['polarity'] = 'pos'

    metaclusters = dda_pipeline(tapp_parameters, input_files, 'tapp_pipeline_test')

    return metaclusters

def full_pipeline_test():
    data_dir = '/data/HYE_DDA_Orbitrap/mzXML/subset/'
    file_names = [
        '1_1.mzXML' , '1_2.mzXML' , '1_3.mzXML' , '1_4.mzXML' , '1_5.mzXML'  ,
        # '1_6.mzXML' , '1_7.mzXML' , '1_8.mzXML' , '1_9.mzXML' , '1_10.mzXML' ,
        '3_1.mzXML' , '3_2.mzXML' , '3_3.mzXML' , '3_4.mzXML' , '3_5.mzXML'  ,
        # '3_6.mzXML' , '3_7.mzXML' , '3_8.mzXML' , '3_9.mzXML' , '3_10.mzXML' ,
        ]
    class_ids = [
        1,1,1,1,1,
        # 1,1,1,1,1,
        3,3,3,3,3,
        # 3,3,3,3,3,
    ]
    tapp_parameters = {
        'instrument_type': 'orbitrap',
        'resolution_ms1': 70000,
        'resolution_msn': 30000,
        'reference_mz': 200,
        'avg_fwhm_rt': 9,
        'num_samples_mz': 5,
        'num_samples_rt': 5,
        'smoothing_coefficient_mz': 0.4,
        'smoothing_coefficient_rt': 0.4,
        'max_peaks': 1000,
        'polarity': 'pos',
        'min_mz': 0,
        'max_mz': 100000,
        'min_rt': 0,
        'max_rt': 100000,
    }

    # Load raw_data, calculate mesh, find peaks.
    raw_data = []
    mesh = []
    peaks = []
    for file_name in file_names:
        print("Extracting peaks for:", file_name)
        r, m, p = peak_extraction(os.path.join(data_dir, file_name), tapp_parameters)
        raw_data += [r]
        mesh += [m]
        peaks += [p]

    # Calculate similarity matrix.
    print("Calculating unwarped similarity matrix.")
    similarity_matrix = np.zeros(len(file_names) ** 2).reshape(len(file_names), len(file_names))
    for i in range(0,len(file_names)):
        file_name = file_names[i]
        peaks_a = peaks[i]
        for j in range(i,len(file_names)):
            peaks_b = peaks[j]
            similarity_matrix[j,i] = tapp.find_similarity(peaks_a, peaks_b, 2000).geometric_ratio
            similarity_matrix[i,j] = similarity_matrix[j,i]
    similarity_matrix_names = [file_name.split('.')[0] for file_name in file_names]
    similarity_matrix_df = pd.DataFrame(similarity_matrix)
    similarity_matrix_df.columns = similarity_matrix_names
    similarity_matrix_df.rename(index=dict(zip(range(0,len(similarity_matrix_names),1), similarity_matrix_names)), inplace=True)
    # plt.ion()
    # plt.figure()
    # import seaborn as sns
    # sns.heatmap(similarity_matrix_df, xticklabels=True, yticklabels=True, square=True, vmin=0, vmax=1)
    # plt.title('Unwarped similarity')

    # Calculate similarity matrix after reference warping.
    print("Calculating reference warping similarity matrix.")
    similarity_matrix = np.zeros(len(file_names) ** 2).reshape(len(file_names), len(file_names))
    ref_peaks = peaks[0]
    warped_peaks = [ref_peaks]
    for i, peaks_b in enumerate(peaks):
        if i != 0:
            warped_peaks += [warp_peaks([ref_peaks, peaks_b], 0, 100, 100, 2000, 0.2, 50)[1]]
    for i in range(0,len(file_names)):
        file_name = file_names[i]
        peaks_a = warped_peaks[i]
        for j in range(i,len(file_names)):
            print("i:", i, "j:", j)
            peaks_b = warped_peaks[j]
            similarity_matrix[j,i] = tapp.find_similarity(peaks_a, peaks_b, 2000).geometric_ratio
            similarity_matrix[i,j] = similarity_matrix[j,i]
    similarity_matrix_names = [file_name.split('.')[0] for file_name in file_names]
    similarity_matrix_df = pd.DataFrame(similarity_matrix)
    similarity_matrix_df.columns = similarity_matrix_names
    similarity_matrix_df.rename(index=dict(zip(range(0,len(similarity_matrix_names),1), similarity_matrix_names)), inplace=True)
    # plt.ion()
    # plt.figure()
    # import seaborn as sns
    # sns.heatmap(similarity_matrix_df, xticklabels=True, yticklabels=True, square=True, vmin=0, vmax=1)
    # plt.title('Reference warping similarity')

    # # Calculate similarity matrix after exhaustive warping.
    # print("Calculating exhaustive warping similarity matrix.")
    # similarity_matrix = np.zeros(len(file_names) ** 2).reshape(len(file_names), len(file_names))
    # for i in range(0,len(file_names)):
        # file_name = file_names[i]
        # peaks_a = peaks[i]
        # for j in range(0,len(file_names)):
            # print("i:", i, "j:", j)
            # peaks_b = peaks[j]
            # peaks_b = warp_peaks([peaks_a, peaks_b], 0, 100, 100, 2000, 0.2, 50)[1]
            # similarity_matrix[j,i] = tapp.find_similarity(peaks_a, peaks_b, 2000).geometric_ratio
            # # similarity_matrix[i,j] = similarity_matrix[j,i]
    # similarity_matrix_names = [file_name.split('.')[0] for file_name in file_names]
    # similarity_matrix_df = pd.DataFrame(similarity_matrix)
    # similarity_matrix_df.columns = similarity_matrix_names
    # similarity_matrix_df.rename(index=dict(zip(range(0,len(similarity_matrix_names),1), similarity_matrix_names)), inplace=True)
    # plt.ion()
    # plt.figure()
    # import seaborn as sns
    # sns.heatmap(similarity_matrix_df, xticklabels=True, yticklabels=True, square=True, vmin=0, vmax=1)
    # plt.title('Exhaustive warping similarity')

    # # Calculate similarity matrix after reference warping found with exhaustive.
    # print("Calculating reference warping similarity matrix after exhaustive similarity search.")
    # similarity_matrix = np.zeros(len(file_names) ** 2).reshape(len(file_names), len(file_names))
    # ref_peaks = peaks[similarity_matrix.sum(axis=0).argmax()]
    # warped_peaks = [ref_peaks]
    # for i, peaks_b in enumerate(peaks):
        # if i != 0:
            # warped_peaks += [warp_peaks([ref_peaks, peaks_b], 0, 100, 100, 2000, 0.2, 50)[1]]
    # for i in range(0,len(file_names)):
        # file_name = file_names[i]
        # peaks_a = warped_peaks[i]
        # for j in range(i,len(file_names)):
            # print("i:", i, "j:", j)
            # peaks_b = warped_peaks[j]
            # similarity_matrix[j,i] = tapp.find_similarity(peaks_a, peaks_b, 2000).geometric_ratio
            # similarity_matrix[i,j] = similarity_matrix[j,i]
    # similarity_matrix_names = [file_name.split('.')[0] for file_name in file_names]
    # similarity_matrix_df = pd.DataFrame(similarity_matrix)
    # similarity_matrix_df.columns = similarity_matrix_names
    # similarity_matrix_df.rename(index=dict(zip(range(0,len(similarity_matrix_names),1), similarity_matrix_names)), inplace=True)
    # plt.ion()
    # plt.figure()
    # import seaborn as sns
    # sns.heatmap(similarity_matrix_df, xticklabels=True, yticklabels=True, square=True, vmin=0, vmax=1)
    # plt.title('Reference warping similarity after exhaustive similarity search')

    # similarity_matrix_names = (sample_groups['group'] + "_" + sample_groups['sample_number'].map(str)).values
    # similarity_matrix_df = pd.DataFrame(similarity_matrix)
    # similarity_matrix_df.columns = similarity_matrix_names
    # similarity_matrix_df.rename(index=dict(zip(range(0,len(similarity_matrix_names),1), similarity_matrix_names)), inplace=True)
    # similarity_output_dir = "{0}".format(output_dir)

    print("Performing metamatch")
    metamatch_input = list(zip(class_ids, warped_peaks))
    metamatch_results = perform_metamatch(metamatch_input, 0.005, 10, 0.7)

    # DEBUG
    metapeaks = pd.DataFrame({
        'file_id': [peak.file_id for peak in metamatch_results.orphans],
        'class_id': [peak.class_id for peak in metamatch_results.orphans],
        'cluster_id': [peak.cluster_id for peak in metamatch_results.orphans],
        'cluster_mz': [peak.cluster_mz for peak in metamatch_results.orphans],
        'cluster_rt': [peak.cluster_rt for peak in metamatch_results.orphans],
        'height': [peak.height for peak in metamatch_results.orphans],
        'local_max_mz': [peak.local_max_mz for peak in metamatch_results.orphans],
        'local_max_rt': [peak.local_max_rt for peak in metamatch_results.orphans],
        })
    metaclusters = pd.DataFrame({
        'cluster_id': [cluster.id for cluster in metamatch_results.clusters],
        'cluster_mz': [cluster.mz for cluster in metamatch_results.clusters],
        'cluster_rt': [cluster.rt for cluster in metamatch_results.clusters],
        'avg_height': [cluster.avg_height for cluster in metamatch_results.clusters],
        })

    for file in file_names:
        metaclusters[file] = 0.0

    for j, cluster in enumerate(metamatch_results.clusters):
        for i, file in enumerate(file_names):
            metaclusters.at[j, file] = cluster.file_heights[i]

    return raw_data, mesh, peaks, warped_peaks, class_ids, metamatch_results, metapeaks, metaclusters

RawData.tic = tic

Peak.plot_xic = plot_xic
Peak.plot_raw_points = plot_raw_points
Peak.plot_raw_roi_sigma = plot_raw_roi_sigma
Peak.plot_theoretical_sigma = plot_theoretical_sigma
Peak.plot_raw_roi_fitted_sigma = plot_raw_roi_fitted_sigma
Peak.plot_raw_roi_fitted_sigma_fast = plot_raw_roi_fitted_sigma_fast
Peak.plot_raw_roi_fitted_sigma_weighted = plot_raw_roi_fitted_sigma_weighted
Peak.plot_slope_descent_sigma = plot_slope_descent_sigma
Peak.plot_sigma = plot_sigma
Peak.fit_height_and_sigmas = fit_height_and_sigmas
Peak.fit_sigmas = fit_sigmas
