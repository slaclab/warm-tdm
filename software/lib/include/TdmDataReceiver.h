
#ifndef __TDM_DATA_RECEIVER_H__
#define __TDM_DATA_RECEIVER_H__

#include <rogue/interfaces/stream/Slave.h>
#include <rogue/interfaces/stream/Frame.h>

#include <s4daq/rogue_data_sender.h>

namespace warm_tdm_lib {

   class TdmDataReceiver : public rogue::interfaces::stream::Slave {

         uint32_t rxFrameCount_;
         uint32_t rxByteCount_;

         std::mutex mtx_;

         std::atomic<bool> senderStop_;
         RogueDataSenderInterface sender_;

      public:

         static std::shared_ptr<warm_tdm_lib::TdmDataReceiver> create(std::string collectorHost, int collectorPort);

         static void setup_python();

         TdmDataReceiver (std::string collectorHost, int collectorPort);

         ~TdmDataReceiver();

         void countReset();

         uint32_t getRxFrameCount() const;

         uint32_t getRxByteCount() const;

         void addDetectorRow(uint8_t groupID, uint8_t columnBoardID, uint8_t rowIndex, uint8_t rowLen=8);

         void initializeCommunication();

         void acceptFrame ( std::shared_ptr<rogue::interfaces::stream::Frame> frame );
   };

   typedef std::shared_ptr<warm_tdm_lib::TdmDataReceiver> TdmDataReceiverPtr;

}

#endif

