import React, { useEffect } from 'react';
import * as Font from 'expo-font';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { CormorantGaramond_600SemiBold } from '@expo-google-fonts/cormorant-garamond';
import { NunitoSans_400Regular, NunitoSans_700Bold } from '@expo-google-fonts/nunito-sans';
import { MobileProduct } from './src/components/MobileProduct';
import { registerWidgetBackgroundSync } from './src/widgets/widgetBackgroundTask';
import { ShareIntentProvider } from 'expo-share-intent';

void Font.loadAsync({ CormorantGaramond_600SemiBold, NunitoSans_400Regular, NunitoSans_700Bold }).catch(() => undefined);

export default function App() {
  useEffect(() => {
    void registerWidgetBackgroundSync().catch(() => undefined);
  }, []);
  return <ShareIntentProvider options={{ scheme: 'mondaiy', resetOnBackground: false }}><SafeAreaProvider><MobileProduct /></SafeAreaProvider></ShareIntentProvider>;
}
