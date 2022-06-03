import auth from '@react-native-firebase/auth';
import React, {useEffect, useState} from 'react';
import database from "@react-native-firebase/database";
import {
    Alert,
    SafeAreaView,
    ScrollView,
    Text,
    TextInput,
    TouchableOpacity,
    useWindowDimensions,
    View
} from "react-native";
import appleAuth from "@invertase/react-native-apple-authentication";
import {GoogleSignin, statusCodes} from "@react-native-google-signin/google-signin";
import {AppleSocialButton, GoogleSocialButton} from "react-native-social-buttons";
import {buttons, fonts, format} from "../style/Styles";
import {KeyboardAwareScrollView} from "react-native-keyboard-aware-scroll-view";

export const SignIn = ({navigation}) => {
    const [email, setEmail] = useState(''),
        [password, setPassword] = useState(''),
        [createEmail, setCreateEmail] = useState(''),
        [createPassword, setCreatePassword] = useState(''),
        dimensions = useWindowDimensions();

    const handleSignUp = async () => {
        try {
            console.log('Attempting to sign up');
            await signUp(createEmail, createPassword);
            navigation.navigate('Tabs');
        } catch (error) {
            Alert.alert('Error signing up', error.message);
        }
    }

    const signUp = async (email, password) => {
        if (password.length < 6) {
            throw new Error('Please use at least 6 characters for your password');
        }

        auth().createUserWithEmailAndPassword(email, password)
            .then(async (userCredential) => {
                Alert.alert('Welcome', 'Your account has been created successfully')
            }).catch(error => {
            if (error.code === 'auth/email-already-in-use') {
                throw new Error('That email address is already in use');
            } else if (error.code === 'auth/invalid-email') {
                throw new Error('That email address is invalid');
            } else {
                throw new Error(error);
            }
        });
    }

    const handleLogIn = async () => {
        try {
            await logIn(email, password);
            Alert.alert('Welcome', 'You have been signed in');
            navigation.navigate('Tabs');
        } catch (error) {
            Alert.alert('Error signing in', error.message);
        }
    }

    const logIn = async (email, password) => {
        auth().signInWithEmailAndPassword(email, password)
            .catch(error => {
                if (error.code === 'auth/wrong-password')
                    throw new Error('Password is incorrect');
                else if (error.code === 'auth/user-not-found')
                    throw new Error('Account was not found with that email');
                else throw new Error(error);
            });
    }

    const handleLogInApple = async () => {
        try {
            await logInApple();
            Alert.alert('Welcome', 'You have been signed in');
            navigation.navigate('Tabs');
        } catch (error) {
            Alert.alert('Error', error.message);
        }
    }

    async function logInApple() {
        const appleAuthRequestResponse = await appleAuth.performRequest({
            requestedOperation: appleAuth.Operation.LOGIN,
            requestedScopes: [appleAuth.Scope.EMAIL, appleAuth.Scope.FULL_NAME],
        });

        if (!appleAuthRequestResponse.identityToken) {
            throw new Error('Apple sign-in failed. Try another method. ');
        }

        const { identityToken, nonce } = appleAuthRequestResponse;
        const appleCredential = auth.AppleAuthProvider.credential(identityToken, nonce);
        await auth().signInWithCredential(appleCredential);
    }

    const handleLogInGoogle = async () => {
        try {
            await logInGoogle();
            Alert.alert('Welcome', 'You have been signed in');
            navigation.navigate('Tabs');
        } catch (error) {
            Alert.alert('Error', error.message);
        }
    }

    const logInGoogle = async () => {
        GoogleSignin.configure({
            webClientId: "141405103878-rsc5n2819h3b7fors0u0oadthfv4dmde.apps.googleusercontent.com",
        });

        try {
            await GoogleSignin.hasPlayServices();
            const {idToken} = await GoogleSignin.signIn();
            const googleCredential = auth.GoogleAuthProvider.credential(idToken);
            await auth().signInWithCredential(googleCredential);
        } catch (error) {
            if (error.code === statusCodes.SIGN_IN_CANCELLED) {
                return true;
            } else if (error.code === statusCodes.IN_PROGRESS) {
                return true;
            } else if (error.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
                throw new Error('Google play services are unavailable, try another login method');
            }
        }
    }

    const handleSendEmail = async () => {
        try {
            await sendEmail();
            Alert.alert('A recovery email has been sent', 'Check your email to recover your account');
        } catch (error) {
            Alert.alert('Error sending email', error.message);
        }
    }

    const sendEmail = async () => {
        await auth().sendPasswordResetEmail(email);
    }

    useEffect(() => {
        const sub = auth().onAuthStateChanged(authChanged);
        return sub;
    }, []);

    function authChanged(user) {
        if (user) {
            navigation.navigate('Tabs');
        } else {
            Alert.alert(
                'Continue without signing in?',
                "You won't be able to sync with other devices",
                [
                    {
                        text: "Sign in or sign up", onPress: () => {
                            console.debug('User chose to sign in')
                        },
                        style: "cancel"
                    },
                    {
                        text: "Continue as guest",
                        onPress: () => {
                            navigation.navigate('Tabs');
                        },
                    }
                ]
            );

        }
    }

    return (
        <SafeAreaView>
            <KeyboardAwareScrollView extraScrollHeight={200} style={{paddingTop: 20}}>
                <View style={{alignItems: 'center', paddingTop: 20, paddingBottom: 10, paddingHorizontal: 40,}}>
                    <Text style={[fonts.mediumText]}>Sign in with existing account</Text>
                </View>
                <View style={{alignItems: 'center', marginTop: 20, marginBottom: 20}}>
                    <AppleSocialButton buttonViewStyle={{width: dimensions.width - 80, marginBottom: 15}} onPress={async () => await handleLogInApple()} />
                    <GoogleSocialButton buttonViewStyle={{width: dimensions.width - 80}} onPress={async () => await handleLogInGoogle()} />
                </View>
                <View>
                    <View style={{alignItems: 'center', paddingTop: 20, paddingBottom: 10, paddingHorizontal: 40,}}>
                        <Text style={[fonts.mediumText]}>Sign in with email</Text>
                    </View>
                    <TextInput underlineColorAndroid='transparent'
                               placeholder='Email address'
                               placeholderTextColor='#aaa'
                               keyboardType='email-address'
                               onChangeText={(email) => setEmail(email)}
                               numberOfLines={1}
                               multiline={false}
                               style={format.textBox}
                               blurOnSubmit={false}/>
                    <TextInput underlineColorAndroid='transparent'
                               placeholder='Password'
                               placeholderTextColor='#aaa'
                               onChangeText={(password) => setPassword(password)}
                               numberOfLines={1}
                               multiline={false}
                               style={format.textBox}
                               blurOnSubmit={false}/>
                </View>
                <TouchableOpacity style={buttons.submitButton}
                                  onPress={async () => await handleLogIn()}>
                    <Text style={[buttons.submitButtonText, ]}>Sign in</Text>
                </TouchableOpacity>
                <TouchableOpacity style={buttons.forgotPasswordButton}
                                  onPress={async () => await handleSendEmail()}>
                    <Text style={buttons.forgotPasswordText}>Forgot your password?</Text>
                </TouchableOpacity>
                <View>
                    <View style={{alignItems: 'center', paddingTop: 20, paddingBottom: 10, paddingHorizontal: 40,}}>
                        <Text style={[fonts.mediumText]}>Register with email</Text>
                    </View>
                    <TextInput
                        underlineColorAndroid='transparent'
                        placeholder='Email address'
                        placeholderTextColor='#aaa'
                        keyboardType='email-address'
                        onChangeText={(email) => setCreateEmail(email)}
                        numberOfLines={1}
                        multiline={false}
                        style={format.textBox}
                        blurOnSubmit={false}/>
                    <TextInput underlineColorAndroid='transparent'
                               placeholder='Password (at least 6 characters)'
                               placeholderTextColor='#aaa'
                               onChangeText={(password) => setCreatePassword(password)}
                               numberOfLines={1}
                               multiline={false}
                               style={format.textBox}
                               blurOnSubmit={false}/>
                </View>
                <TouchableOpacity style={buttons.submitButton} onPress={async () => await handleSignUp()}>
                    <Text style={buttons.submitButtonText}>Create Account</Text>
                </TouchableOpacity>
            </KeyboardAwareScrollView>
        </SafeAreaView>
    );
}