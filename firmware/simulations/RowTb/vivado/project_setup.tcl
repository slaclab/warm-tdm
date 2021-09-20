set_property target_language Verilog [current_project]
set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY none [get_runs synth_1]
#set_property STEPS.SYNTH_DESIGN.ARGS.BUFG 32 [get_runs synth_1]

#set_property STEPS.POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
#set_property STEPS.POST_PLACE_POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
#set_property STEPS.OPT_DESIGN.ARGS.DIRECTIVE NoBramPowerOpt [get_runs impl_1]

#set_property STEPS.SYNTH_DESIGN.ARGS.FANOUT_LIMIT 500 [get_runs synth_1]
#set_property STEPS.SYNTH_DESIGN.ARGS.FSM_EXTRACTION one_hot [get_runs synth_1]
#set_property STEPS.SYNTH_DESIGN.ARGS.KEEP_EQUIVALENT_REGISTERS true [get_runs synth_1]
#set_property STEPS.SYNTH_DESIGN.ARGS.NO_LC true [get_runs synth_1]
#set_property STEPS.SYNTH_DESIGN.ARGS.SHREG_MIN_SIZE 5 [get_runs synth_1]


#set_property STEPS.PLACE_DESIGN.ARGS.DIRECTIVE ExtraPostPlacementOpt [get_runs impl_1]
#set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
#set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AddRetime [get_runs impl_1]
#set_property STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE MoreGlobalIterations [get_runs impl_1]


