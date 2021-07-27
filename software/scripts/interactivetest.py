import pyrogue.interfaces
from TDMSubroutines import *



def SetLoopParameters(group,low,high,step):
	for lowval in [group.SaFbLowOffset,group.SaBiasLowOffset,
					group.FasFluxLowOffset,group.Sq1FbLowOffset,
					group.Sq1BiasLowOffset,group.TesBiasLowOffset]:
		lowval.set(value=low)
			
	for highval in [group.SaFbHighOffset,group.SaBiasHighOffset,
					group.FasFluxHighOffset,group.Sq1FbHighOffset,
					group.Sq1BiasHighOffset,group.TesBiasHighOffset]:
		highval.set(value=high)

	for stepsize in [group.SaFbStepSize,group.SaBiasStepSize,
					group.FasFluxStepSize,group.Sq1FbStepSize,
					group.Sq1BiasStepSize,group.TesBiasStepSize]:
		stepsize.set(value=step)



vc = pyrogue.interfaces.VirtualClient()

group = vc.root.Group

SetLoopParameters(group,1,3,1) #Set the loop parameters to arbitary values


x = saTune(group,0)

#Testing saFluxBias
# data = saFluxBias(group,1,1)
# print(data)

# print("saFluxBias done")