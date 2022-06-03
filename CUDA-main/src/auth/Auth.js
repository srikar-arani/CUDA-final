import {GoogleSignin} from "@react-native-google-signin/google-signin";
import auth from "@react-native-firebase/auth";
import {Alert} from "react-native";

export const logOut = async (navigation) => {
    GoogleSignin.signOut()
        .then(() => {
            auth().signOut()
                .then(() => {
                    navigation.navigate('SignIn');
                })
                .catch(() => {
                    console.error('Error signing out');
                });
        }).catch(() => {
        auth().signOut()
            .then(() => {
                navigation.navigate('SignIn');
            })
            .catch(() => {
                console.error('Error signing out');
            });
    });
}

export const disconnectFromOrganization = (userInfo) => {
    userInfo.userData.ref.update({organization: null})
        .catch(() => {
            Alert.alert('Error', 'A problem was encountered while disconnecting');
        });
}