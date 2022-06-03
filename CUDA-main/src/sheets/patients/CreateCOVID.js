import React, {useState} from 'react';
import RBSheet from "react-native-raw-bottom-sheet";
import {buttons, fonts, format, rbSheetStyle} from "../../style/Styles";
import {Alert, ScrollView, Text, TextInput, TouchableOpacity, useWindowDimensions, View} from "react-native";
import useAuth from "../../auth/UserContext";
import {KeyboardAwareScrollView} from "react-native-keyboard-aware-scroll-view";
import database from "@react-native-firebase/database";

export const CreateCOVID = ({modalRef}) => {
    const [patientName, setPatientName] = useState(''),
        [patientEmail, setPatientEmail] = useState(''),
        userInfo = useAuth(),
        patientsRef = database().ref(userInfo.patientsRefPath + '/covid-patients/'),
        dimensions = useWindowDimensions();

    const registerPatient = () => {
        const patientReference = patientsRef.push();
        patientReference.update({
            name: patientName,
            email: patientEmail
        }).then(() => modalRef.current?.close())
        .catch((error) => Alert.alert('Error', error));
    }


    return (
        <RBSheet ref={modalRef} height={dimensions.height * 0.75} customStyles={rbSheetStyle}>
            <KeyboardAwareScrollView extraScrollHeight={200} style={{paddingTop: 20}}>
                <Text style={[fonts.smallText, {paddingBottom: 20}]}>
                    All fields are optional and can be edited after the patient is created
                </Text>
                <Text style={[fonts.mediumText, {paddingBottom: 10}]}>Name</Text>
                <TextInput underlineColorAndroid='transparent'
                           placeholder='Name'
                           placeholderTextColor='#aaa'
                           keyboardType='default'
                           onChangeText={(patientName) => setPatientName(patientName)}
                           numberOfLines={1}
                           multiline={false}
                           style={format.textBox}
                           blurOnSubmit={false}/>
                <Text style={[fonts.mediumText, {paddingBottom: 10}]}>Contact Info</Text>
                <TextInput
                    underlineColorAndroid='transparent'
                    placeholder='Email address'
                    placeholderTextColor='#aaa'
                    keyboardType='email-address'
                    onChangeText={(patientEmail) => setPatientEmail(patientEmail)}
                    numberOfLines={1}
                    multiline={false}
                    style={format.textBox}
                    blurOnSubmit={false}/>
                <TouchableOpacity
                    style={buttons.submitButton}
                    onPress={() => registerPatient()}>
                    <Text style={buttons.submitButtonText}>Create Patient</Text>
                </TouchableOpacity>
            </KeyboardAwareScrollView>
        </RBSheet>
    );
}