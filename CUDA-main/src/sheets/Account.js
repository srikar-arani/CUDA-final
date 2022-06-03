import React, {useState} from 'react';
import RBSheet from "react-native-raw-bottom-sheet";
import {buttons, device, fonts, format, rbSheetStyle} from "../style/Styles";
import {ActivityIndicator, Alert, Text, TextInput, TouchableOpacity, useWindowDimensions, View} from "react-native";
import {ScrollView} from "react-native-gesture-handler";
import {disconnectFromOrganization, logOut} from "../auth/Auth";
import useAuth from "../auth/UserContext";
import database from "@react-native-firebase/database";
import {KeyboardAwareScrollView} from "react-native-keyboard-aware-scroll-view";

export const Account = ({navigation, modalRef}) => {
    const userInfo = useAuth(),
        organization = userInfo.user?.organization,
        dimensions = useWindowDimensions(),
        [addCode, setAddCode] = useState(-1),
        [connectAddCode, setConnectAddCode] = useState(-1),
        [name, setName] = useState('');

    const disconnect = async () => {
        let name = 'organization';

        await database().ref('organizations/' + organization)
            .once('value')
            .then((organizationSnapshot) => {
                if (organizationSnapshot.exists())
                    name = organizationSnapshot.val()['name'];
            });
        await disconnectFromOrganization(userInfo);
        Alert.alert('Success', 'You are now disconnected from ' + name);
    }

    const handleConnectOrganization = async () => {
        try {
            await connectOrganization(connectAddCode);
            let name = 'organization';
            await database().ref('organizations/' + organization)
                .once('value')
                .then((organizationSnapshot) => {
                    if (organizationSnapshot.exists())
                        name = organizationSnapshot.val()['name'];
                });
        } catch (error) {
            Alert.alert('Error', error.message);
        }
    }

    const connectOrganization = async (connectAddCode) => {
        // transaction to search org with add code, create user associated with that org
        if (connectAddCode >= 0 && connectAddCode.toString().length >= 4) {
            database().ref('organizations/')
                .orderByChild('addCode').equalTo(connectAddCode)
                .once('value',
                    (snapshot) => {
                        if (snapshot.exists()) {
                            snapshot.forEach((organization) => {
                                // organization with add code exists
                                userInfo.userData.ref.update({
                                    organization: organization.key
                                }).then(() => {
                                    Alert.alert('Success', 'Synced with ' + organization.val().name)
                                    modalRef.current?.close();
                                });
                            })
                        } else {
                            Alert.alert('No organization found', 'Please re-enter your add code');
                        }
                    }).catch(() => {
                Alert.alert('No organization found', 'Please re-enter your add code');
            });
        } else {
            throw new Error('Please enter a valid add code');
        }
    };

    const registerOrganization = () => {
        if (name !== '' && addCode.toString().length >= 4) {
            const newOrganization = database().ref('/organizations').push();
            newOrganization.set({
                name: name,
                addCode: addCode
            }).then(() => {
                database().ref(userInfo.userRefPath).update({
                    organization: organization.key
                }).then(() => {
                    Alert.alert('Registration complete', 'Now syncing with ' + organization.val().name)
                    modalRef.current?.close();
                }).catch((error) => {
                    Alert.alert('Error', error.message);
                })
            }).catch((error) => {
                Alert.alert('Error', error.message);
            });
        } else Alert.alert('Error', 'Please enter both an organization name and an add code');
    };

    const handleLogOut = () => logOut(navigation).then(() => modalRef.current?.close());

    return (
        <RBSheet ref={modalRef} height={dimensions.height * 0.25} customStyles={rbSheetStyle}>
            <KeyboardAwareScrollView extraScrollHeight={200} style={{paddingTop: 20}}>
                {
                    (userInfo.loginStatus === 'registered')
                        ? <View>
                            <TouchableOpacity style={{
                                flex: 1,
                                flexDirection: 'row',
                                justifyContent: 'center',
                                marginVertical: 10,
                                marginHorizontal: 20,
                                borderRadius: 5,
                                paddingVertical: 10,
                                paddingHorizontal: 15,
                                backgroundColor: '#fff',
                            }}
                                              onPress={() => handleLogOut()}>
                                <Text style={fonts.mediumText}>Logout</Text>
                            </TouchableOpacity>
                        </View> : null
                }
                {
                    (userInfo.loginStatus === 'guest')
                        ? <View>
                            <TouchableOpacity style={{
                                flex: 1,
                                flexDirection: 'row',
                                justifyContent: 'center',
                                marginVertical: 10,
                                marginHorizontal: 20,
                                borderRadius: 5,
                                paddingVertical: 10,
                                paddingHorizontal: 15,
                                backgroundColor: '#fff',
                            }}
                                              onPress={() => navigation.navigate('SignIn')}>
                                <Text style={fonts.mediumText}>Return to sign in</Text>
                            </TouchableOpacity>
                        </View> : null
                }
                {
                    (!organization && userInfo.loginStatus === 'registered')
                        ? <>
                            <View style={{paddingTop: 20}}>
                                <Text style={fonts.smallText}>
                                    Organizations make it possible to sync data with any number of other people and devices. Connect
                                    using an add code, or create one with just a small amount of information.
                                </Text>
                            </View>
                            <View style={{alignItems: 'center', paddingTop: 30, paddingBottom: 10, paddingHorizontal: 40,}}>
                                <Text style={fonts.mediumText}>Sync to existing</Text>
                            </View>
                            <Text style={[fonts.mediumText, format.fieldName]}>Organization add code *</Text>
                            <TextInput style={format.textBox}
                                       underlineColorAndroid='transparent'
                                       placeholder='At least 4 digits'
                                       placeholderTextColor='#aaa'
                                       keyboardType='numeric'
                                       onChangeText={(code) => setConnectAddCode(code)}
                                       numberOfLines={1}
                                       multiline={false}
                                       maxLength={8}
                                       blurOnSubmit={false}/>
                            <TouchableOpacity style={buttons.submitButton}
                                              onPress={() => handleConnectOrganization()}>
                                <Text style={buttons.submitButtonText}>Connect and Sync</Text>
                            </TouchableOpacity>
                            <View>
                                <View style={{alignItems: 'center', paddingTop: 30, paddingBottom: 10, paddingHorizontal: 40,}}>
                                    <Text style={[fonts.mediumText]}>
                                        Create new and sync
                                    </Text>
                                </View>
                                <Text style={[fonts.mediumText, format.fieldName]}>Name *</Text>
                                <TextInput underlineColorAndroid='transparent'
                                           placeholder='Name *'
                                           placeholderTextColor='#aaa'
                                           keyboardType='default'
                                           onChangeText={(newName) => setName(newName)}
                                           numberOfLines={1}
                                           multiline={false}
                                           style={format.textBox}
                                           blurOnSubmit={false}/>
                            </View>
                            <View>
                                <Text style={[fonts.mediumText, format.fieldName]}>Add Code *</Text>
                                <Text style={fonts.smallText}>This unique code is used for apps to connect to this
                                    organization</Text>
                                <TextInput underlineColorAndroid='transparent'
                                           placeholder='4+ digits *'
                                           placeholderTextColor='#aaa'
                                           keyboardType='numeric'
                                           onChangeText={(code) => setAddCode(code)}
                                           numberOfLines={1}
                                           maxLength={8}
                                           multiline={false}
                                           style={format.textBox}
                                           blurOnSubmit={false}/>
                            </View>
                            <TouchableOpacity style={buttons.submitButton} onPress={() => registerOrganization()}>
                                <Text style={buttons.submitButtonText}>Create Organization</Text>
                            </TouchableOpacity>
                        </> : null
                }

                {
                    (userInfo.loginStatus === 'registered')
                        ? <View>
                            <TouchableOpacity style={{
                                flex: 1,
                                flexDirection: 'row',
                                justifyContent: 'center',
                                marginVertical: 10,
                                marginHorizontal: 20,
                                borderRadius: 5,
                                paddingVertical: 10,
                                paddingHorizontal: 15,
                                backgroundColor: '#fff',
                            }} onPress={() => disconnect()}>
                                <Text style={[fonts.mediumText]}>Disconnect from organization</Text>
                            </TouchableOpacity>
                        </View> : null
                }
                {
                    (userInfo.loginStatus === 'loading' || userInfo.loginStatus === 'signed-out')
                        ? <ActivityIndicator style={{padding: 15}} size={'large'}/>
                        : null
                }
            </KeyboardAwareScrollView>
        </RBSheet>);
}