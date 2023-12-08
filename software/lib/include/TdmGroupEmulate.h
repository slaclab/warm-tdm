
#ifndef __TDM_GROUP_EMULATE_H__
#define __TDM_GROUP_EMULATE_H__

#include <rogue/interfaces/stream/Master.h>
#include <rogue/interfaces/stream/Frame.h>
#include <rogue/interfaces/stream/FrameIterator.h>
#include <atomic>
#include <thread>

namespace warm_tdm_lib {

   class TdmGroupEmulate : public rogue::interfaces::stream::Master {

         std::atomic<uint32_t> timestampA_;
         std::atomic<uint32_t> timestampB_;
         std::atomic<uint32_t> timestampC_;
         std::atomic<uint32_t> reqCount_;
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

         uint8_t getGroupId() const;

         void setNumColBoards(uint8_t number);

         uint8_t getNumColBoards() const;

         void setNumRows(uint8_t number);

         uint8_t getNumRows() const;

         void start();

         void stop();

         void countReset();

         uint32_t getTxFrameCount() const;

         uint32_t getTxByteCount() const;

         void reqFrames(uint32_t timestampA, uint32_t timestampB, uint32_t timestampC);

         void genFrames();
   };

   typedef std::shared_ptr<warm_tdm_lib::TdmGroupEmulate> TdmGroupEmulatePtr;

}

#endif

