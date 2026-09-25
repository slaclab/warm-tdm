
#ifndef __TDM_GROUP_EMULATE_H__
#define __TDM_GROUP_EMULATE_H__

#include <rogue/interfaces/stream/Master.h>
#include <rogue/interfaces/stream/Frame.h>
#include <rogue/interfaces/stream/FrameIterator.h>
#include <thread>

namespace warm_tdm_lib {

   class TdmGroupEmulate : public rogue::interfaces::stream::Master {

         uint32_t timestampA_;
         uint32_t timestampB_;
         uint32_t timestampC_;
         uint32_t reqCount_;
         uint32_t sequence_;
         uint32_t txFrameCount_;
         uint32_t txByteCount_;
         uint8_t  groupId_;
         uint8_t  numColBoards_;
         uint8_t  numRows_;
         bool runEnable_;
         std::thread* txThread_;

         void runThread();

      public:

         static std::shared_ptr<warm_tdm_lib::TdmGroupEmulate> create(uint8_t groupId);

         static void setup_python();

         TdmGroupEmulate (uint8_t groupId);

         ~TdmGroupEmulate ();

         void setNumColBoards(uint8_t number);

         uint8_t getNumColBoards();

         void setNumRows(uint8_t number);

         uint8_t getNumRows();

         void start();

         void stop();

         void countReset();

         uint32_t getTxFrameCount();

         uint32_t getTxByteCount();

         void reqFrames(uint32_t timestampA, uint32_t timestampB, uint32_t timestampC);

         void genFrames();
   };

   typedef std::shared_ptr<warm_tdm_lib::TdmGroupEmulate> TdmGroupEmulatePtr;

}

#endif

