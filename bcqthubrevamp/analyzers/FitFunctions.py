import numpy as np
import warnings

def exponential_decay(t, A, T1, C):
    return A * np.exp(-t / T1) + C

def sine_wave(t, A, lin_freq, phi=0):
    warnings.warn("Untested!!")
    
    return A * np.sin(2 * np.pi * lin_freq * t + phi)

def get_fft_freq(signal, dt):
    warnings.warn("Untested!!")
    n = len(signal)
    return np.fft.rfftfreq(n, dt)

def get_fft_magnitude(signal):
    warnings.warn("Untested!!")
    return np.abs(np.fft.rfft(signal))

def gaussian(x, mu, sigma):
    warnings.warn("Untested!!")
    return np.exp(-0.5 * ((x - mu) / sigma) ** 2)

def linear(x, m, b):
    return m * x + b

def denser(x: np.ndarray, num_points: int = 5000):
    start, end = x[0], x[-1]
    return np.linspace(start, end, num_points)