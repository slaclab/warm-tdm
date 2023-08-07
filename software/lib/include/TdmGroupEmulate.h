
#ifndef __TDM_GROUP_EMULATE_H__
#define __TDM_GROUP_EMULATE_H__

#include <rogue/interfaces/stream/Master.h>
#include <rogue/interfaces/stream/Frame.h>
#include <rogue/interfaces/stream/FrameIterator.h>

namespace warm_tdm_lib {

   class TdmGroupEmulate : public rogue::interfaces::stream::Master {

         uint64_t lastTimestamp_;
         uint64_t reqTimestamp_;
         uint32_t sequence_;
         uint32_t txFrameCount_;
         uint32_t txByteCount_;
         uint8_t  groupId_;
         uint8_t  numColBoards_;
         uint8_t  numRows_;
         bool runEnable_;

      public:

         static std::shared_ptr<ucsc_hn_lib::TdmGroupEmulate> create(uint8_t groupId, uint8_t numColBoards, uint8_t numRows);

         static void setup_python();

         TdmGroupEmulate (uint8_t groupId, uint8_t numColBoards, uint8_t numRows);

         ~TdmGroupEmulate ();

         void start();

         void stop();

         void countReset();

         uint32_t getTxFrameCount();

         uint32_t getTxByteCount();

         void reqFrames(uint64_t timestamp);

         void genFrames();

         void runThread();
   };

   typedef std::shared_ptr<ucsc_hn_lib::TdmGroupEmulate> TdmGroupEmulatePtr;

}

#endif

