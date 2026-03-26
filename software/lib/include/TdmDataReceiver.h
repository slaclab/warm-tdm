
#ifndef __TDM_DATA_RECEIVER_H__
#define __TDM_DATA_RECEIVER_H__

#include <rogue/interfaces/stream/Slave.h>
#include <rogue/interfaces/stream/Frame.h>

namespace warm_tdm_lib {

   class TdmDataReceiver : public rogue::interfaces::stream::Slave {

         uint32_t rxFrameCount_;
         uint32_t rxByteCount_;

         std::mutex mtx_;

      public:

         static std::shared_ptr<warm_tdm_lib::TdmDataReceiver> create();

         static void setup_python();

         TdmDataReceiver ();

         void countReset();

         uint32_t getRxFrameCount();

         uint32_t getRxByteCount();

         void acceptFrame ( std::shared_ptr<rogue::interfaces::stream::Frame> frame );
   };

   typedef std::shared_ptr<warm_tdm_lib::TdmDataReceiver> TdmDataReceiverPtr;

}

#endif

