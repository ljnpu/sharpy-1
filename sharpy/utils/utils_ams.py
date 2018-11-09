'''
ams: utilities
'''
from mpl_toolkits.mplot3d import axes3d
import matplotlib.pyplot as plt
import ipdb

def plot_xy(x, y):
    plt.plot(x, y)
    # plt.ylabel('some numbers')
    plt.show()

def plot_wireframe(x, y, z):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_wireframe(x, y, z)
    plt.show()

def spy(M):
    plt.spy(M)
    plt.show()