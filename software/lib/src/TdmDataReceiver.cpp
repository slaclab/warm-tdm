#define __STDC_FORMAT_MACROS
#include <inttypes.h>
#include <TdmDataReceiver.h>
#include <rogue/interfaces/stream/Slave.h>
#include <rogue/interfaces/stream/Frame.h>
#include <rogue/interfaces/stream/FrameIterator.h>
#include <rogue/interfaces/stream/FrameAccessor.h>
#include <rogue/interfaces/stream/FrameLock.h>
#include <rogue/GilRelease.h>
#include <boost/python.hpp>

namespace ris = rogue::interfaces::stream;
namespace bp = boost::python;

warm_tdm_lib::TdmDataReceiverPtr warm_tdm_lib::TdmDataReceiver::create() {
   warm_tdm_lib::TdmDataReceiverPtr r = std::make_shared<warm_tdm_lib::TdmDataReceiver>();
   return(r);
}

void warm_tdm_lib::TdmDataReceiver::setup_python() {
   bp::class_<warm_tdm_lib::TdmDataReceiver, warm_tdm_lib::TdmDataReceiverPtr, bp::bases<ris::Slave>, boost::noncopyable >("TdmDataReceiver",bp::init<>())
      .def("countReset",         &warm_tdm_lib::TdmDataReceiver::countReset)
      .def("getRxFrameCount",    &warm_tdm_lib::TdmDataReceiver::getRxFrameCount)
      .def("getRxByteCount",     &warm_tdm_lib::TdmDataReceiver::getRxByteCount)
   ;
}

warm_tdm_lib::TdmDataReceiver::TdmDataReceiver () {
   countReset();
}

void warm_tdm_lib::TdmDataReceiver::countReset () {
   rxFrameCount_ = 0;
   rxByteCount_ = 0;
}

uint32_t warm_tdm_lib::TdmDataReceiver::getRxFrameCount() {
   return rxFrameCount_;
}

uint32_t warm_tdm_lib::TdmDataReceiver::getRxByteCount() {
   return rxByteCount_;
}

void warm_tdm_lib::TdmDataReceiver::acceptFrame ( ris::FramePtr frame ) {
   rogue::GilRelease noGil;
   ris::FrameLockPtr lock = frame->lock();

   rxFrameCount_++;
   rxByteCount_ += frame->getPayload();
}

