#define __STDC_FORMAT_MACROS
#include <inttypes.h>
#include <boost/python.hpp>
#include <TdmDataReceiver.h>
#include <TdmGroupEmulate.h>

BOOST_PYTHON_MODULE(warm_tdm_lib) {
   PyEval_InitThreads();
   try {
      warm_tdm_lib::TdmDataReceiver::setup_python();
      warm_tdm_lib::TdmGroupEmulate::setup_python();
   } catch (...) {
      printf("Failed to load module. import rogue first\n");
   }
   printf("Loaded warm_tdm_lib\n");
};
