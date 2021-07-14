import pyrogue.interfaces
from TDMSubroutines import *



def SetLoopParameters(group,step,high,low):
	for stepsize in [group.SaFbStepSize,group.SaBiasStepSize,
					group.FasFluxStepSize,group.Sq1FbStepSize,
					group.Sq1BiasStepSize,group.TesBiasStepSize]:
		stepsize.set(value=step)

	for highval in [group.SaFbHighOffset,group.SaBiasHighOffset,
					group.FasFluxHighOffset,group.Sq1FbHighOffset,
					group.Sq1BiasHighOffset,group.TesBiasHighOffset]:
		highval.set(value=high)

	for lowval in [group.SaFbLowOffset,group.SaBiasLowOffset,
					group.FasFluxLowOffset,group.Sq1FbLowOffset,
					group.Sq1BiasLowOffset,group.TesBiasLowOffset]:
		lowval.set(value=low)

vc = pyrogue.interfaces.VirtualClient()
group = vc.root.Group
SetLoopParameters(group,1,3,0)

data = saFluxBias(group)
print("saFluxBias done")