import React from 'react';
import {NavigationContainer} from '@react-navigation/native';
import IconE from 'react-native-vector-icons/Entypo';
import IconMI from 'react-native-vector-icons/MaterialIcons'
import {backgroundColor, mediumPurple, tabNavigatorStyle} from '../style/Styles';
import {AnimatedTabBarNavigator,} from 'react-native-animated-nav-tab-bar'
import {createStackNavigator} from "@react-navigation/stack";
import {createBottomTabNavigator} from "@react-navigation/bottom-tabs";
import Devices from "../screens/Devices";
import Data from "../screens/Data";
import {SignIn} from "../screens/SignIn";
import {UserProvider} from "../auth/UserContext";

export const Stack = createStackNavigator();
export const Tab = createBottomTabNavigator();
export const screenOptions = {headerShown: false};
const Tabs = AnimatedTabBarNavigator();

const Navigator = () => (
    <UserProvider>
        <NavigationContainer>
            <Stack.Navigator initialRouteName='SignIn'>
                <Stack.Screen
                    name='SignIn'
                    component={SignIn}
                    options={{headerShown: false}}
                />
                <Stack.Screen
                    name='Tabs'
                    component={TabsNavigator}
                    options={{headerShown: false}}
                />
            </Stack.Navigator>
        </NavigationContainer>
    </UserProvider>
);

const TabsNavigator = () => (
    <Tabs.Navigator
        initialRouteName='MonitorTab'
        screenOptions={tabNavigatorStyle}
        tabBarOptions={{
            activeTintColor: mediumPurple,
            inactiveTintColor: mediumPurple,
            activeBackgroundColor: backgroundColor,
            inactiveBackgroundColor: backgroundColor
        }}
        appearance={{
            floating: true,
            activeColors: [mediumPurple, mediumPurple],
            activeTabBackgrounds: [backgroundColor, backgroundColor]
        }}>
        <Tabs.Screen
            name='MonitorTab'
            component={Devices}
            options={{
                title: 'Devices',
                headerShown: false,
                tabBarIcon: ({ focused, color, size }) => (
                    <IconMI name='device-hub' color={color} size={size}/>
                ),
            }}
        />
        <Tabs.Screen
            name='ViewDataTab'
            component={Data}
            options={{
                title: 'Records',
                headerShown: false,
                tabBarIcon: ({ focused, color, size }) => (
                    <IconE name='area-graph' color={color} size={size}/>
                ),
            }}
        />
    </Tabs.Navigator>
)



export default Navigator;