import React, {useState} from 'react';
import RBSheet from "react-native-raw-bottom-sheet";
import {buttons, fonts, format, rbSheetStyle} from "../../style/Styles";
import {Alert, ScrollView, Text, TextInput, TouchableOpacity, useWindowDimensions} from "react-native";
import useAuth from "../../auth/UserContext";
import database from "@react-native-firebase/database";
import {KeyboardAwareScrollView} from "react-native-keyboard-aware-scroll-view";

export const EditCOVID = ({modalRef, patientKey}) => {
    const [patientName, setPatientName] = useState(''),
        [patientEmail, setPatientEmail] = useState(''),
        [patientPhone, setPatientPhone] = useState(0),
        userInfo = useAuth(),
        patientRef = database().ref(userInfo.patientsRefPath + '/covid-patients/' + patientKey),
        dimensions = useWindowDimensions();

    const updatePatient = () => {
        let patient = null;
        patientRef.once('value', (patientSnapshot) => {
            if (patientSnapshot.val()) {
                if (patientName !== patientSnapshot.val().name && patientName !== '') {
                    patient.update({name: patientName});
                }

                if (patientEmail !== patientSnapshot.val().email && patientEmail !== '') {
                    patient.update({email: patientEmail});
                }

                if (patientPhone !== patientSnapshot.val().phone && patientPhone !== '') {
                    patient.update({phone: patientPhone});
                }
            }
        }).then(() => {
            Alert.alert('Success', 'Changes have been applied')
            modalRef.current?.close();
        }).catch((error) => Alert.alert('Error', error));
    }


    return (
        <RBSheet ref={modalRef} height={dimensions.height * 0.75} customStyles={rbSheetStyle}>
            <KeyboardAwareScrollView extraScrollHeight={200} style={{paddingTop: 20}}>
                <Text style={fonts.heading}>Edit Patient Info</Text>
                <Text style={fonts.smallText}>All fields are optional and can always be edited</Text>
                <Text style={[fonts.mediumText, format.fieldName]}>Name</Text>
                <TextInput underlineColorAndroid='transparent'
                           placeholder='Name'
                           placeholderTextColor='#aaa'
                           keyboardType='default'
                           onChangeText={(patientName) => setPatientName(patientName)}
                           numberOfLines={1}
                           multiline={false}
                           style={format.textBox}
                           blurOnSubmit={false}/>
                <Text style={[fonts.mediumText, format.fieldName]}>Email</Text>
                <TextInput underlineColorAndroid='transparent'
                           placeholder='Email address'
                           placeholderTextColor='#aaa'
                           keyboardType='email-address'
                           onChangeText={(patientEmail) => setPatientEmail(patientEmail)}
                           numberOfLines={1}
                           multiline={false}
                           style={format.textBox}
                           blurOnSubmit={false}/>
                <Text style={[fonts.mediumText, format.fieldName]}>Phone</Text>
                <TextInput underlineColorAndroid='transparent'
                           placeholder='Phone number'
                           placeholderTextColor='#aaa'
                           keyboardType='numeric'
                           onChangeText={(patientPhone) => setPatientPhone(patientPhone)}
                           numberOfLines={1}
                           multiline={false}
                           style={format.textBox}
                           blurOnSubmit={false}/>
                <TouchableOpacity style={buttons.submitButton}
                                  onPress={() => updatePatient()}>
                    <Text style={buttons.submitButtonText}>Apply Changes</Text>
                </TouchableOpacity>
            </KeyboardAwareScrollView>
        </RBSheet>);
}