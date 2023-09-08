#define __STDC_FORMAT_MACROS
#include <inttypes.h>
#include <TdmDataReceiver.h>
#include <rogue/interfaces/stream/Slave.h>
#include <rogue/interfaces/stream/Frame.h>
#include <rogue/interfaces/stream/FrameIterator.h>
#include <rogue/interfaces/stream/FrameAccessor.h>
#include <rogue/interfaces/stream/FrameLock.h>
#ifndef NO_PYTHON
#include <rogue/GilRelease.h>
#include <boost/python.hpp>

namespace bp = boost::python;
#endif

namespace ris = rogue::interfaces::stream;

warm_tdm_lib::TdmDataReceiverPtr warm_tdm_lib::TdmDataReceiver::create(std::string collectorHost, int collectorPort) {
   warm_tdm_lib::TdmDataReceiverPtr r = std::make_shared<warm_tdm_lib::TdmDataReceiver>(collectorHost, collectorPort);
   return(r);
}

#ifndef NO_PYTHON
void warm_tdm_lib::TdmDataReceiver::setup_python() {
   bp::class_<warm_tdm_lib::TdmDataReceiver, warm_tdm_lib::TdmDataReceiverPtr, bp::bases<ris::Slave>, boost::noncopyable >("TdmDataReceiver",bp::init<std::string, int>())
      .def("countReset",              &warm_tdm_lib::TdmDataReceiver::countReset)
      .def("getRxFrameCount",         &warm_tdm_lib::TdmDataReceiver::getRxFrameCount)
      .def("getRxByteCount",          &warm_tdm_lib::TdmDataReceiver::getRxByteCount)
      .def("addDetectorRow",          &warm_tdm_lib::TdmDataReceiver::addDetectorRow)
      .def("initializeCommunication", &warm_tdm_lib::TdmDataReceiver::initializeCommunication)
   ;
}
#endif

warm_tdm_lib::TdmDataReceiver::TdmDataReceiver (std::string collectorHost, int collectorPort) :
senderStop_(false),
sender_(collectorHost, collectorPort, senderStop_)
{
   countReset();
}

warm_tdm_lib::TdmDataReceiver::~TdmDataReceiver() {
	senderStop_ = true; // instruct sender_ to shut down its background thread
}

void warm_tdm_lib::TdmDataReceiver::countReset () {
   rxFrameCount_ = 0;
   rxByteCount_ = 0;
}

uint32_t warm_tdm_lib::TdmDataReceiver::getRxFrameCount() const {
   return rxFrameCount_;
}

uint32_t warm_tdm_lib::TdmDataReceiver::getRxByteCount() const {
   return rxByteCount_;
}

void warm_tdm_lib::TdmDataReceiver::addDetectorRow(uint8_t groupID, uint8_t columnBoardID, uint8_t rowIndex, uint8_t rowLen) {
   sender_.addDetectorRow(groupID, columnBoardID, rowIndex, rowLen);
}

void warm_tdm_lib::TdmDataReceiver::initializeCommunication() {
   sender_.initializeCommunication();
}

void warm_tdm_lib::TdmDataReceiver::acceptFrame ( ris::FramePtr frame ) {
#ifndef NO_PYTHON
   rogue::GilRelease noGil;
#endif
   ris::FrameLockPtr lock = frame->lock();
   sender_.ingestFrame(frame);

   {
      std::lock_guard<std::mutex> lock(mtx_);
      rxFrameCount_++;
      rxByteCount_ += frame->getPayload();
   }
}

