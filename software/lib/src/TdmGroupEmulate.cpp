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

warm_tdm_lib::TdmGroupEmulatePtr warm_tdm_lib::TdmGroupEmulate::create(uint8_t groupId, uint8_t numColBoards, uint8_t numRows) {
   warm_tdm_lib::TdmGroupEmulatePtr r = std::make_shared<warm_tdm_lib::TdmGroupEmulate>(groupId,numColBoards,numRows);
   return(r);
}

void warm_tdm_lib::TdmGroupEmulate::setup_python() {
   bp::class_<warm_tdm_lib::TdmGroupEmulate, warm_tdm_lib::TdmGroupEmulatePtr, bp::bases<ris::Master>, boost::noncopyable >("TdmGroupEmulate",bp::init<uint8_t, uint8_t, uint8_t>())
      .def("_start",             &warm_tdm_lib::TdmGroupEmulate::start)
      .def("_stop",              &warm_tdm_lib::TdmGroupEmulate::stop)
      .def("reqFrames",          &warm_tdm_lib::TdmGroupEmulate::countReset)
      .def("countReset",         &warm_tdm_lib::TdmGroupEmulate::countReset)
      .def("getTxFrameCount",    &warm_tdm_lib::TdmGroupEmulate::getTxFrameCount)
      .def("getTxByteCount",     &warm_tdm_lib::TdmGroupEmulate::getTxByteCount)
   ;
}

warm_tdm_lib::TdmGroupEmulate::TdmGroupEmulate (uint8_t groupId, uint8_t numColBoards, uint8_t numRows) {
   countReset();

   lastTimestamp_ = 0;
   reqTimestamp_ = 0;
   groupId_ = groupId;
   numColBoards_ = numColBoards;
   numRows_ = numRows;
   runEnable_ = false;
   txThread_ = NULL;
   sequence_ = 0;
}

warm_tdm_lib::TdmGroupEmulate::~TdmGroupEmulate () {
   stop();
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

void warm_tdm_lib::TdmGroupEmulate::reqFrames(uint64_t timestamp) {
   reqTimestamp_ = timestamp;
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

   lastTimestamp_ = reqTimestamp_;
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
      toFrame(it, 8, &lastTimestamp_);

      tmp32 = 0;
      toFrame(it, 4, &tmp32);

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
            toFrame(it, 4, &x);
            toFrame(it, 4, &row);
            toFrame(it, 4, &col);
            toFrame(it, 4, &groupId_);
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
      if ( lastTimestamp_ != reqTimestamp_ ) genFrames();
      else usleep(10);
   }
}

