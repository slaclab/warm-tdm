#define __STDC_FORMAT_MACROS
#include <inttypes.h>
#include <TdmGroupEmulate.h>
#include <rogue/interfaces/stream/Master.h>
#include <rogue/interfaces/stream/Frame.h>
#include <rogue/interfaces/stream/FrameIterator.h>
#include <rogue/interfaces/stream/FrameAccessor.h>
#include <rogue/interfaces/stream/FrameLock.h>
#include <rogue/GilRelease.h>
#include <boost/python.hpp>

namespace ris = rogue::interfaces::stream;
namespace bp = boost::python;

warm_tdm_lib::TdmGroupEmulatePtr warm_tdm_lib::TdmGroupEmulate::create(uint8_t groupId) {
   warm_tdm_lib::TdmGroupEmulatePtr r = std::make_shared<warm_tdm_lib::TdmGroupEmulate>(groupId);
   return(r);
}

void warm_tdm_lib::TdmGroupEmulate::setup_python() {
   bp::class_<warm_tdm_lib::TdmGroupEmulate, warm_tdm_lib::TdmGroupEmulatePtr, bp::bases<ris::Master>, boost::noncopyable >("TdmGroupEmulate",bp::init<uint8_t>())
      .def("_start",             &warm_tdm_lib::TdmGroupEmulate::start)
      .def("_stop",              &warm_tdm_lib::TdmGroupEmulate::stop)
      .def("getNumColBoards",    &warm_tdm_lib::TdmGroupEmulate::getNumColBoards)
      .def("setNumColBoards",    &warm_tdm_lib::TdmGroupEmulate::setNumColBoards)
      .def("getNumRows",         &warm_tdm_lib::TdmGroupEmulate::getNumRows)
      .def("setNumRows",         &warm_tdm_lib::TdmGroupEmulate::setNumRows)
      .def("reqFrames",          &warm_tdm_lib::TdmGroupEmulate::reqFrames)
      .def("countReset",         &warm_tdm_lib::TdmGroupEmulate::countReset)
      .def("getTxFrameCount",    &warm_tdm_lib::TdmGroupEmulate::getTxFrameCount)
      .def("getTxByteCount",     &warm_tdm_lib::TdmGroupEmulate::getTxByteCount)
   ;
}

warm_tdm_lib::TdmGroupEmulate::TdmGroupEmulate (uint8_t groupId) {
   countReset();

   groupId_ = groupId;
   timestampA_ = 0;
   timestampB_ = 0;
   timestampC_ = 0;
   reqCount_ = 0;
   sequence_ = 0;
   numColBoards_ = 1;
   numRows_ = 1;
   runEnable_ = false;
   txThread_ = NULL;
   sequence_ = 0;
}

warm_tdm_lib::TdmGroupEmulate::~TdmGroupEmulate () {
   stop();
}

void warm_tdm_lib::TdmGroupEmulate::setNumColBoards(uint8_t number) {
   numColBoards_ = number;
}

uint8_t warm_tdm_lib::TdmGroupEmulate::getNumColBoards() {
   return numColBoards_;
}

void warm_tdm_lib::TdmGroupEmulate::setNumRows(uint8_t number) {
   numRows_ = number;
}

uint8_t warm_tdm_lib::TdmGroupEmulate::getNumRows() {
   return numRows_;
}

void warm_tdm_lib::TdmGroupEmulate::start() {
   if ( txThread_ == NULL ) {
      runEnable_ = true;
      txThread_ = new std::thread(&TdmGroupEmulate::runThread, this);
   }
}

void warm_tdm_lib::TdmGroupEmulate::stop() {
   if ( txThread_ != NULL ) {
      runEnable_ = false;
      txThread_->join();
      delete txThread_;
      txThread_ = NULL;
   }
}

void warm_tdm_lib::TdmGroupEmulate::countReset () {
   txFrameCount_ = 0;
   txByteCount_ = 0;
}

uint32_t warm_tdm_lib::TdmGroupEmulate::getTxFrameCount() {
   return txFrameCount_;
}

uint32_t warm_tdm_lib::TdmGroupEmulate::getTxByteCount() {
   return txByteCount_;
}

void warm_tdm_lib::TdmGroupEmulate::reqFrames(uint32_t timestampA, uint32_t timestampB, uint32_t timestampC) {
   ++reqCount_;
   timestampA = timestampA;
   timestampB = timestampB;
   timestampC = timestampC;
}

void warm_tdm_lib::TdmGroupEmulate::genFrames() {
   rogue::interfaces::stream::FramePtr frame;
   rogue::interfaces::stream::FrameIterator it;

   uint8_t  col;
   uint8_t  row;
   uint8_t  x;
   uint32_t size;
   uint8_t  tmp8;
   uint32_t tmp32;
   uint64_t tmp64;

   size = 24 + (36 * numRows_);

   for ( col=0; col < numColBoards_; col++ ) {
      frame = reqFrame(size, true);
      frame->setPayload(size);
      it = frame->begin();

      tmp8 = 0xAA;
      toFrame(it, 1, &tmp8);

      toFrame(it, 1, &groupId_);
      toFrame(it, 1, &x);
      toFrame(it, 1, &numRows_);
      toFrame(it, 4, &timestampA_);
      toFrame(it, 4, &timestampB_);
      toFrame(it, 4, &timestampC_);

      toFrame(it, 4, &sequence_);

      tmp8 = 0;
      toFrame(it, 1, &tmp8);

      tmp32 = 0;
      toFrame(it, 3, &tmp32);

      for (row=0; row < numRows_; row++) {
         toFrame(it, 1, &row);

         tmp32 = 0;
         toFrame(it, 3, &tmp32);

         for (x=0; x < 8; x++) {
            toFrame(it, 1, &x);
            toFrame(it, 1, &row);
            toFrame(it, 1, &col);
            toFrame(it, 1, &groupId_);
         }
      }
      sendFrame(frame);
      ++txFrameCount_;
      txByteCount_ += size;
   }
   ++sequence_;
}

void warm_tdm_lib::TdmGroupEmulate::runThread() {
   while (runEnable_) {
      if ( reqCount_ > sequence_ ) genFrames();
      else usleep(10);
   }
}

