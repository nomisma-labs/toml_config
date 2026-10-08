# Learning tcfg by example

Nomisma **tcfg** (pronounced “tee-config”) language defines application configuration using [TOML 1.1](https://toml.io/en/v1.1.0).
The purpose of this language is to add structural features to TOML configs, i.e. ability to compose a single valid config from several fragments. For those who are familiar with OOP this reminds "inheritance" and "aggregation". So instead of redefining potentially complex multi-component config for different purposes we define "base" config with some default parameters and then re-use it by extending it in "derived" configs (inheritance) or by defining common parameters in "donor" config and including parts or whole "donor" into an "acceptor" config (aggregation). Those are main structural mechanisms. Apart from it there would be "adjustment" instructions that controls how these extension (aka inheritance) or aggregation (aka import or inclusion) happens.

**tcfg** files by convention have `.tcfg` file extension. The name of the tcfg file will have its special meaning when we come to integration with Nomisma build system, but in this guide we can use any name (usually just app.tcfg). Nomisma platform provides a tool to generate well formed TOML configs from tcfg config so they can be used by Nomisma apps in different case.

Just to make it more illustrative let's consider `md_capture` app that have 2 configs - for dev and prod environments:
```
dev:
    log.level = debug
    connection
        snapshot.address = wss://ws-api.binance.com:443/ws-api/v3
        address = wss://stream-sbe.binance.com:9443/ws
    subscription
        symbols = btcusdt
        channels = trade, depth
    mdLog.file = binance-spot-%Y%m%d-%H.md

prod:
    log
        level = warn
        file = log/%Y%m%d/md_capture.log
    connection
        snapshot.address = wss://ws-api.binance.com:443/ws-api/v3
        address = wss://stream-sbe.binance.com:9443/ws
    subscription
        symbols = btcusdt, ethusdt
        channels = trade, depth
    mdLog.file = md/%Y%m%d/binance-spot-%Y%m%d-%H.md
```
As you see even in this small config there are repeating and unique parameters and values. There are multiple ways how we can abstract them out. But first - why would we want to do it?
Here are the cases:
1. A trader/quant maintains a list of required symbols for MD capture. He wants to focus on this list only and not to get into details of app configuration. For that he creates a file `binance-spot-md-capture-symbols.toml` and adds the required symbols there. On the other hand a dev, while testing the MD capture app, wants to focus on specific list of symbols (perhaps only one symbol for simplicity).
2. An infra team monitors the connection parameters of Binance MD end point. They learned that Binance migrated to a new infra with different DNS address. Infra team wants to apply this new address for all components homogenously - for that they maintain a single `binance-spot-connection.toml` config which contains actual connectivity parameters, so they don't need to update configs of 20+ apps that connect to Binance market data end point. However one trader learned that one particular subscription channel that he subscribes (e.g. liquidation info) was not migrated properly by Binance, so he wants his app to use old connectivity parameters - so he applies an exception to his app config.

One possible way of defining a coherent config for this app and use cases is to:
1. Create base config which would be also a dev config, e.g. `md_capture.toml` with complete dev config;
2. Create `md_capture.tcfg` which in `base` case inherits `md_capture.toml`;
3. Add `ci` section for integration environment that inherits base config and imports `binance-spot-connection.toml`. It also updates parameters `log` and `mdLog` to standard values for infra deployment;
4. Add `prod` section for main production deployment and inherit it from `ci`. Update `subscription.symbols` parameter - by including it from `binance-spot-md-capture-symbols.toml`;
5. Add `prod-liquidation` section to collect liquidation data, inherit it from `prod` and update the whole `subscription` parameter section.

As you see, by defining configuration this way we allowed several teams (dev, QA, devops/infra, researchers, traders) to collaborate and not to step on each other toes while configuring and using md_capture app.
