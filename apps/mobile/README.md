# Mondaiy Mobile

Native iOS/Android client for Mondaiy, built with React Native and Expo.

## Mobile experience

The default surface is a native React Native product, not a WebView. It applies
the Mondaiy visual system to mobile-native onboarding, authentication, daily
briefing, discovery, search, assistant, notifications, profile and settings.
The layout respects safe areas, uses 44px+ touch targets and keeps primary
navigation within thumb reach.

## Native foundations

- Email/password authentication using the production API.
- Tokens stored in the platform secure keystore.
- Ask the Mondaiy agent from the mobile composer.
- Read proposed tasks and confirm them.
- One-thumb bottom pill navigation: Home, Menu, Ask, Notifications, Search.

## Run locally

```bash
cp .env.example .env
npm install
npx expo start
```

Use `npm run android` or `npm run ios` to launch an emulator. Set
`EXPO_PUBLIC_WEB_APP_URL` to a staging web workspace when testing a non-production environment.

## Release

Install the EAS CLI, authenticate to the Expo account that owns this project,
then build a distributable binary:

```bash
npx eas-cli build --platform android --profile preview
npx eas-cli build --platform ios --profile production
```
