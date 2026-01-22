# Hanshin The Hue CVNET Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/github/license/jgreys/ha-thehue)](LICENSE)
[![GitHub release](https://img.shields.io/github/release/jgreys/ha-thehue.svg)](https://github.com/jgreys/ha-thehue/releases/)

[한국어 문서](README_KO.md) | English

A Home Assistant custom integration for Hanshin The Hue apartments using the CVNET smart home system.

## Features

### 🏠 Climate Control
- **Room Temperature Monitoring**: Real-time temperature sensors for all rooms
- **Individual Room Heating**: Control heating for each room independently
- **Living Room**: Special control with on/off functionality

### 💡 Lighting Control  
- **Individual Light Control**: Control lights in each room
- **All Lights Switch**: Turn all lights on/off at once
- **Real-time Status**: See current on/off state of each light

### 👥 Visitor Management
- **Visitor List**: View recent visitors with timestamps
- **Visitor Camera**: See visitor photos automatically
- **Pagination**: Browse through visitor history
- **Real-time Notifications**: Get alerts when new visitors arrive

### 🚗 Car Entrance Monitoring
- **Entry/Exit Log**: Track vehicle entries and exits
- **License Plate Recognition**: View license plate information
- **Timestamp Records**: See exact entry/exit times
- **Notifications**: Get alerts for vehicle movements

### 📊 Utility Monitoring
- **Electricity Usage**: Monitor power consumption (kWh)
- **Water Usage**: Track water consumption (m³)
- **Gas Usage**: Monitor gas consumption (m³)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add `https://github.com/jgreys/ha-thehue` as repository
5. Select category "Integration" and click "Add"
6. Find "Hanshin The Hue CVNET" and install
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub releases](https://github.com/jgreys/ha-thehue/releases)
2. Extract the archive
3. Copy the `cvnet` folder to `<config>/custom_components/`
4. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Hanshin The Hue CVNET"
4. Enter your CVNET credentials:
   - **Username**: Your apartment CVNET username
   - **Password**: Your CVNET password

## Supported Devices

After setup, you'll see these devices:

### 📟 Telemeter
- Electricity sensor (kWh)
- Water sensor (m³)  
- Gas sensor (m³)

### 🔥 Heating
- Living room temperature sensor
- Room 1-3 temperature sensors
- Individual room climate controls

### 💡 Lights
- Individual room light controls
- All lights master switch

### 👥 Visitors
- Visitor count sensor
- Visitor camera
- Visitor list with pagination controls
- Visitor snapshot selector

### 🚗 Car Entrance
- Car entry count sensor
- Entry/exit history
- Pagination controls

## Services

The integration provides these services:

### `cvnet.force_refresh`
Manually refresh all CVNET data
```yaml
service: cvnet.force_refresh
```

### `cvnet.clear_session`  
Clear authentication session (useful for troubleshooting)
```yaml
service: cvnet.clear_session
```

### `cvnet.session_info`
Get current session information
```yaml
service: cvnet.session_info
```

## Automation Examples

### Visitor Alert
```yaml
automation:
  - alias: "Visitor Alert"
    trigger:
      - platform: state
        entity_id: sensor.visitors
        attribute: visitor_count
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.visitor_count > trigger.from_state.attributes.visitor_count }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "New visitor detected!"
```

### Energy Monitoring
```yaml
automation:
  - alias: "High Energy Usage Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.electricity
        above: 100
    action:
      - service: notify.persistent_notification
        data:
          message: "High electricity usage: {{ states('sensor.electricity') }} kWh"
```

### Auto Heating Schedule
```yaml
automation:
  - alias: "Morning Heating"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.living_room_heating
        data:
          temperature: 22
```

## Troubleshooting

### Authentication Issues
If you get authentication errors:
1. Verify your credentials in the CVNET web interface
2. Use the `cvnet.clear_session` service
3. Wait a few minutes and try again

### Connection Problems  
- Check your internet connection
- Ensure CVNET service is available
- Try the `cvnet.force_refresh` service

### Missing Entities
- Some features may not be available in all apartment configurations
- Check the Home Assistant logs for specific error messages

## Multi-language Support

This integration supports:
- 🇺🇸 **English**
- 🇰🇷 **한국어 (Korean)**

Language is automatically selected based on your Home Assistant language settings.

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration created by the community. It is not affiliated with Hanshin The Hue or CVNET.

## Support

- 🐛 [Report Issues](https://github.com/jgreys/ha-thehue/issues)
- 💬 [Discussions](https://github.com/jgreys/ha-thehue/discussions)
- 📖 [Wiki](https://github.com/jgreys/ha-thehue/wiki)