import auth from '@react-native-firebase/auth';
import React, {createContext, useContext, useEffect, useState} from 'react';
import database from "@react-native-firebase/database";
import DeviceInfo from 'react-native-device-info';

const userAuthContext = createContext({
    user: undefined,                                // the current user's data
    dataInfo: {loginStatus: 'loading'},             // any data stored in userRefPath of database
    loginStatus: 'loading',                         // user login status ('registered', 'offline')
    userRefPath: '/users/offline',                  // current path to user in database
    patientsRefPath: '/users/offline/patients',     // current path to patients in database
    initializing: true,                             // status of auth session
    userAuth: undefined                             // the current user auth (from firebase auth)
});

export const useAuth = () => useContext(userAuthContext);

export const UserProvider: React.FC = ({children}) => {
    const [userAuth, setUserAuth] = useState(() => auth().currentUser);
    const [userData, setUserData] = useState({loginStatus: 'guest'});
    const [userRefPath, setUserRefPath] = useState(() => '/users/offline');
    const [patientsRefPath, setPatientsRefPath] = useState(() => '/users/offline/patients');
    const [initializing, setInitializing] = useState(userAuth === null);

    useEffect(() => auth().onAuthStateChanged((user) => {
        if(!user) {
                const UID = DeviceInfo.getUniqueId();
                setUserAuth(null);
                setUserRefPath('/users/' + UID);
                setPatientsRefPath('/users/' + UID + '/patients');
                setUserData({
                    loginStatus: 'guest',
                    user: null
                });
        } else {
                const userPath = '/users/' + user.uid;
                const userRef = database().ref(userPath);
                setUserAuth(user);
                setUserRefPath(userPath);

                userRef.once('value', (snapshot) => {
                    let orgID = snapshot.val().organization;
                    if(orgID) {
                        setPatientsRefPath('/organizations/' + orgID + '/patients');
                    } else {
                        setPatientsRefPath('/users/' + user.uid);
                    }
                }).then(() => {
                    return userRef.on('value',
                        (snapshot) => {
                            setUserData({
                                loginStatus: 'registered',
                                get user() {
                                    return snapshot.val()
                                }
                            });
                        },
                        (error) => setUserData({
                            loginStatus: 'error',
                            user: null
                        }));
                })
        }

        if (initializing) setInitializing(false);
    }), []);

    return (
        <userAuthContext.Provider
            value={{
                get user() {
                    return userData.user
                },
                userData: userData,
                loginStatus: userData.loginStatus,
                userAuth: userAuth,
                userRefPath: userRefPath,
                patientsRefPath: patientsRefPath,
                initializing,
            }}
        >
            {children}
        </userAuthContext.Provider>
    );
}

export default useAuth;