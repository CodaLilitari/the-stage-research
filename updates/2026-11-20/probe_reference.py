"""First Leaf. Independent empty-history information integral for one actuator."""
import math
import numpy as np
from scipy.special import roots_hermitenorm


def information(order, gain_sd=.3, reading_sd=.1):
    # Three partitions assign the actuator to X and three assign it to Y.
    # By axis symmetry it suffices to integrate the log density ratio given X.
    grid, weights = roots_hermitenorm(order)
    weights = weights / math.sqrt(2 * math.pi)
    broad = reading_sd**2 + gain_sd**2
    narrow = reading_sd**2
    x2 = broad * grid[:, None]**2
    y2 = narrow * grid[None, :]**2
    log_y_over_x = .5 * (y2 - x2) * (1 / narrow - 1 / broad)
    integrand = math.log(2) - np.logaddexp(0., log_y_over_x)
    return float(weights @ integrand @ weights)


if __name__ == '__main__':
    for order in (48, 96, 192, 384):
        print(order, information(order))
    assert abs(information(192) - information(384)) < 1.e-6
    assert abs(information(96, gain_sd=0)) < 1.e-14
