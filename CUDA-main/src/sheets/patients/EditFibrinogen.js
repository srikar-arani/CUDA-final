import React, {useState} from 'react';
import RBSheet from "react-native-raw-bottom-sheet";
import {Alert, ScrollView, Text, TextInput, TouchableOpacity, useWindowDimensions, View} from 'react-native';
import database from "@react-native-firebase/database";
import {buttons, fonts, format, rbSheetStyle} from '../../style/Styles';
import {useAuth} from "../../auth/UserContext";
import {Picker} from "@react-native-picker/picker";
import {KeyboardAwareScrollView} from "react-native-keyboard-aware-scroll-view";

export const EditFibrinogen = ({modalRef, patientKey}) => {
    const [patientName, setPatientName] = useState(null),
        [patientBloodType, setPatientBloodType] = useState(null),
        [patientSex, setPatientSex] = useState(null),
        [patientAge, setPatientAge] = useState(null),
        [patientHeight, setPatientHeight] = useState(null),
        [patientWeight, setPatientWeight] = useState(null),
        userInfo = useAuth(),
        patientRef = database().ref(userInfo.patientsRefPath + '/fibrinogen-patients/' + patientKey),
        dimensions = useWindowDimensions();

    const updatePatient = () => {
        patientRef.once('value', async function (patientSnapshot) {
            if (patientSnapshot.val()) {
                if (patientName !== patientSnapshot.val().name && patientName !== null) {
                    await patientRef.update({name: patientName});
                }

                if (patientBloodType !== patientSnapshot.val().bloodType && patientBloodType !== null) {
                    await patientRef.update({bloodType: patientBloodType});
                }

                if (patientSex !== patientSnapshot.val().sex && patientSex !== null) {
                    await patientRef.update({sex: patientSex});
                }

                if (patientAge !== patientSnapshot.val().age && patientAge !== null) {
                    await patientRef.update({age: patientAge});
                }

                if (patientWeight !== patientSnapshot.val().weight && patientWeight !== null) {
                    await patientRef.update({weight: patientWeight});
                }

                if (patientHeight !== patientSnapshot.val().height && patientHeight !== null) {
                    await patientRef.update({height: patientHeight});
                }
            }
        }).then(() => {
            Alert.alert('Success', 'Changes have been applied');
            modalRef.current?.close();
        }).catch((error) => Alert.alert('Error', error));
    }

    const BloodTypeSelector = () => (
        <View>
            <View style={{flexDirection: 'row', padding: 10, justifyContent: 'center'}}>
                <TouchableOpacity style={(patientBloodType === 'A+') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('A+')}>
                    <Text style={fonts.selectButtonText}>A+</Text>
                </TouchableOpacity>
                <TouchableOpacity style={(patientBloodType === 'B+') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('B+')}>
                    <Text style={fonts.selectButtonText}>B+</Text>
                </TouchableOpacity>
                <TouchableOpacity style={(patientBloodType === 'AB+') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('AB+')}>
                    <Text style={fonts.selectButtonText}>AB+</Text>
                </TouchableOpacity>
                <TouchableOpacity style={(patientBloodType === 'O+') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('O+')}>
                    <Text style={fonts.selectButtonText}>O+</Text>
                </TouchableOpacity>
            </View>
            <View style={{flexDirection: 'row', padding: 10, justifyContent: 'center'}}>
                <TouchableOpacity style={(patientBloodType === 'A-') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('A-')}>
                    <Text style={fonts.selectButtonText}>A-</Text>
                </TouchableOpacity>
                <TouchableOpacity style={(patientBloodType === 'B-') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('B-')}>
                    <Text style={fonts.selectButtonText}>B-</Text>
                </TouchableOpacity>
                <TouchableOpacity style={(patientBloodType === 'AB-') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('AB-')}>
                    <Text style={fonts.selectButtonText}>AB-</Text>
                </TouchableOpacity>
                <TouchableOpacity style={(patientBloodType === 'O-') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                                  onPress={() => setPatientBloodType('O-')}>
                    <Text style={fonts.selectButtonText}>O-</Text>
                </TouchableOpacity>
            </View>
        </View>
    );

    const SexSelector = () => (
        <View style={{flexDirection: 'row', padding: 10, justifyContent: 'center'}}>
            <TouchableOpacity style={(patientSex === 'Male') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                              onPress={() => setPatientSex('Male')}>
                <Text style={fonts.selectButtonText}>Male</Text>
            </TouchableOpacity>
            <TouchableOpacity style={(patientSex === 'Female') ? buttons.bloodTypeSelectButton : buttons.unselectedBloodTypeButton}
                              onPress={() => setPatientSex('Female')}>
                <Text style={fonts.selectButtonText}>Female</Text>
            </TouchableOpacity>
        </View>
    );

    const AgeSelector = () => {
        let ages = [];
        for (let i = 0; i < 100; ++i)
            ages.push(i);

        return (
            <Picker itemStyle={{color: '#fff'}}
                    selectedValue={patientAge}
                    onValueChange={(itemValue, itemIndex) => setPatientAge(itemValue)}>
                {
                    ages.map((prop, key) => {
                            return <Picker.Item key={key} label={key.toString()} value={key.toString()}/>
                        }
                    )}
            </Picker>
        );
    }

    const [feet, setFeet] = useState(null);
    const [inch, setInch] = useState(null);

    const HeightSelector = () => {
        let feetChoices = [];
        for (let i = 0; i <= 7; ++i)
            feetChoices.push(i);

        let inchChoices = [];
        for (let i = 0; i <= 11; ++i)
            inchChoices.push(i);

        return (
            <View style={{flexDirection: 'row'}}>
                <Picker style={{flexDirection: 'row', flex: 1}}
                        itemStyle={{color: '#fff', flexDirection: 'row', flex: 1}}
                        selectedValue={feet}
                        onValueChange={(itemValue, itemIndex) => {
                            setFeet(itemValue);
                            setPatientHeight(itemValue + 'ft. ' + inch + ' in.');
                        }}>
                    {
                        feetChoices.map((prop, key) => {
                                return <Picker.Item key={key} label={key.toString()} value={key.toString()}/>
                            }
                        )}
                </Picker>
                <View style={{justifyContent: 'center', alignItems: 'center'}}>
                    <Text style={fonts.mediumText}>ft.</Text>
                </View>
                <Picker style={{flexDirection: 'row', flex: 1}}
                        itemStyle={{color: '#fff', flexDirection: 'row', flex: 1}}
                        selectedValue={inch}
                        onValueChange={(itemValue, itemIndex) => {
                            setInch(itemValue);
                            setPatientHeight(feet + ' ft. ' + itemValue + ' in.');
                        }}>
                    {
                        inchChoices.map((prop, key) => {
                                return <Picker.Item key={key} label={key.toString()} value={key.toString()}/>
                            }
                        )}
                </Picker>
                <View style={{justifyContent: 'center', alignItems: 'center'}}>
                    <Text style={fonts.mediumText}>in.</Text>
                </View>
            </View>
        )
    }

    return (
        <RBSheet ref={modalRef} height={dimensions.height * 0.75} customStyles={rbSheetStyle}>
            <KeyboardAwareScrollView extraScrollHeight={200} style={{paddingTop: 20}}>
                <Text style={fonts.heading}>Edit Patient Info</Text>
                <Text style={fonts.smallText}>All fields are optional and can be edited after creation</Text>
                <Text style={fonts.subheadingSpaced}>Name</Text>
                <TextInput underlineColorAndroid='transparent'
                           placeholder='Name'
                           placeholderTextColor='#aaa'
                           keyboardType='default'
                           onChangeText={(patientName) => setPatientName(patientName)}
                           numberOfLines={1}
                           multiline={false}
                           style={format.textBox}
                           blurOnSubmit={false} />
                <Text style={fonts.subheadingSpaced}>Blood Type</Text>
                <BloodTypeSelector/>
                <Text style={fonts.subheadingSpaced}>Sex</Text>
                <SexSelector/>
                <Text style={fonts.subheadingSpaced}>Weight</Text>
                <TextInput underlineColorAndroid='transparent'
                           placeholder='Weight (lb.)'
                           placeholderTextColor='#aaa'
                           keyboardType='numeric'
                           onChangeText={(patientWeight) => setPatientWeight(patientWeight + ' lb.')}
                           numberOfLines={1}
                           multiline={false}
                           style={format.textBox}
                           blurOnSubmit={false} />
                <Text style={fonts.subheadingSpaced}>Age</Text>
                <AgeSelector/>
                <Text style={fonts.subheadingSpaced}>Height</Text>
                <HeightSelector/>
                <TouchableOpacity style={buttons.submitButton} onPress={() => updatePatient()}>
                    <Text style={buttons.submitButtonText}>Apply Changes</Text>
                </TouchableOpacity>
            </KeyboardAwareScrollView>
        </RBSheet>
    );
}