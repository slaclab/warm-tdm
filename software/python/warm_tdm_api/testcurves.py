from _CurveClass import *

#below code should work once curveclass has been changed to work with numpy

curvelist = np.array([Curve(30,np.array([5,6,7,8])),Curve(31,np.array([1,2,3,4])),Curve(32,np.array([10,11,12,13])),Curve(33,np.array([2,3,4,5]))])

c = CurveData(np.array([1,2,3,4]),curvelist)

print("\n" + str(c))

#c.plot()
