import React from 'react';
import RBSheet from "react-native-raw-bottom-sheet";
import {backgroundColor, rbSheetStyle} from "../style/Styles";
import {SafeAreaView, useWindowDimensions, View} from "react-native";
import useAuth from "../auth/UserContext";
import QRCodeScanner from "react-native-qrcode-scanner";
import {RNCamera} from "react-native-camera";

const QRScanSheet = ({scanSheetRef}) => {
    const dimensions = useWindowDimensions();
    const userInfo = useAuth();

    return <RBSheet ref={scanSheetRef} height={dimensions.height * 0.55} customStyles={rbSheetStyle}>
        <SafeAreaView style={[{flexGrow: 1, backgroundColor: backgroundColor}]}>
            <View style={{flex: 1, alignContent: 'flex-start'}}>
                <QRCodeScanner
                    onRead={(e) => {console.log(e.data)}}
                    containerStyle={{flex: 0.5, margin: 20, alignContent: 'flex-start', justifyContent: 'flex-start'}}
                    cameraContainerStyle={{borderRadius: 15, overflow: 'hidden', padding: 0, margin: 0}}
                    flashMode={RNCamera.Constants.FlashMode.auto}
                />
            </View>
        </SafeAreaView>
    </RBSheet>;
}

export default QRScanSheet;