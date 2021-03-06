<template>
  <v-app id="web-app">
    <v-app-bar color="white" class="elevation-1" dense app absolute clipped-right>
      <v-toolbar-items>
        <jupyter-widget :widget="item.widget" v-for="item in tool_items" :key="item.name"></jupyter-widget>
      </v-toolbar-items>
      <v-spacer></v-spacer>
      <v-divider vertical></v-divider>
      <v-toolbar-items>
        <v-btn icon @click="drawer = !drawer">
          <v-icon v-if="drawer">mdi-toy-brick-remove</v-icon>
          <v-icon v-else>mdi-toy-brick-plus</v-icon>
        </v-btn>
      </v-toolbar-items>
    </v-app-bar>

    <v-content
      :style="checkNotebookContext() ? 'height: ' + settings.context.notebook.max_height : ''"
    >
      <v-container class="fill-height pa-0" fluid>
        <v-row align="center" justify="center" class="fill-height pa-0 ma-0" style="width: 100%">
          <v-col cols="12" class="fill-height pa-0 ma-0" style="width: 100%">
            <splitpanes class="default-theme" @resize="relayout">
              <pane size="80">
                <v-card tile class="ma-2" style="height: calc(100% - 16px)">
                  <golden-layout
                    @stateChanged="consle.log($event)"
                    :style="checkNotebookContext() ? 'height: 100%;' : 'height: calc(100vh - 64px)'"
                    @selection-changed="consle.log($event)"
                    :has-headers="settings.visible.tab_headers"
                  >
                    <gl-row
                      @stateChanged="consle.log($event)"
                      @selection-changed="consle.log($event)"
                      :closable="false"
                    >
                      <gl-stack
                        v-for="(stack, index) in stack_items"
                        :key="index"
                        @selection-changed="consle.log($event)"
                        :show-maximise-icon="false"
                      >
                        <gl-component
                          v-for="(viewer, index) in stack.viewers"
                          :key="index"
                          title="Test"
                          @resize="relayout"
                        >
                          <v-card tile flat style="height: calc(100% - 2px); margin-top: -2px;">
                            <v-toolbar
                              dense
                              floating
                              absolute
                              right
                              :collapse="viewer.collapse"
                              elevation="1"
                              :width="viewer.collapse ? '48px' : null"
                            >
                              <v-toolbar-items>
                                <v-btn icon @click="viewer.collapse = !viewer.collapse">
                                  <v-icon v-if="viewer.collapse">mdi-menu</v-icon>
                                  <v-icon v-else>mdi-menu-open</v-icon>
                                </v-btn>
                                <v-divider vertical></v-divider>
                                <jupyter-widget :widget="viewer.tools"></jupyter-widget>
                                <v-menu
                                  offset-y
                                  :close-on-content-click="false"
                                  style="z-index: 10"
                                >
                                  <template v-slot:activator="{ on }">
                                    <v-btn icon color="primary" v-on="on">
                                      <v-icon>mdi-settings</v-icon>
                                    </v-btn>
                                  </template>

                                  <v-tabs v-model="viewer.tab" grow height="36px">
                                    <v-tab key="0">Data</v-tab>
                                    <v-tab key="1">Layer</v-tab>
                                    <v-tab key="2">Viewer</v-tab>
                                  </v-tabs>

                                  <v-tabs-items
                                    v-model="viewer.tab"
                                    style="max-height: 500px; width: 350px;"
                                  >
                                    <v-tab-item
                                      key="0"
                                      class="overflow-y-auto"
                                      style="height: 450px"
                                    >
                                      <v-treeview
                                        dense
                                        selectable
                                        :items="data_items"
                                        v-model="viewer.selected_data_items"
                                        hoverable
                                        activatable
                                        item-disabled="locked"
                                        @update:active="console.log($event)"
                                        @input="data_item_selected(viewer)"
                                      ></v-treeview>
                                    </v-tab-item>

                                    <v-tab-item
                                      key="1"
                                      eager
                                      class="overflow-y-auto"
                                      style="height: 100%"
                                    >
                                      <jupyter-widget :widget="viewer.layer_options" />
                                    </v-tab-item>

                                    <v-tab-item
                                      key="2"
                                      eager
                                      class="overflow-y-auto"
                                      style="height: 100%"
                                    >
                                      <jupyter-widget :widget="viewer.viewer_options" />
                                    </v-tab-item>
                                  </v-tabs-items>
                                </v-menu>
                              </v-toolbar-items>
                            </v-toolbar>
                            <jupyter-widget
                              :widget="viewer.widget"
                              style="width: 100%; height: 100%"
                            />
                          </v-card>
                        </gl-component>
                      </gl-stack>
                    </gl-row>
                  </golden-layout>
                </v-card>
                <!-- </pane>
                </splitpanes>-->
              </pane>
              <pane size="20" v-if="drawer">
                <splitpanes horizontal class="elevation-2">
                  <pane>
                    <v-card tile class="ma-2" style="height: calc(100% - 16px)">
                      <golden-layout
                        :style="checkNotebookContext() ? 'height: 100%;' : 'height: calc(100vh - 64px)'"
                      >
                        <gl-stack
                          @stateChanged="consle.log($event)"
                          @selection-changed="consle.log($event)"
                          :closable="false"
                        >
                          <gl-component v-for="(tray, index) in tray_items" :key="index" :title="tray.name">
                            <jupyter-widget :widget="tray.widget"></jupyter-widget>
                          </gl-component>
                        </gl-stack>
                      </golden-layout>
                    </v-card>
                  </pane>
                </splitpanes>
              </pane>
            </splitpanes>
          </v-col>
        </v-row>
      </v-container>
    </v-content>
  </v-app>
</template>

<script>
export default {
  methods: {
    checkNotebookContext() {
      this.notebook_context = document.getElementById("ipython-main-app");
      return this.notebook_context;
    }
  }
};
</script>

<style id="web-app">
.v-toolbar__content {
  padding-left: 0px;
  padding-right: 0px;
}

.v-tabs-items {
  height: 100%;
}

.splitpanes__splitter {
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.2), 0 2px 5px 0 rgba(0, 0, 0, 0.19);
}

.lm_goldenlayout {
  background: #fafafa;
}

.lm_content {
  background: #ffffff;
  border: none;
  border-top: 1px solid #cccccc;
}

.lm_splitter {
  background: #999999;
  opacity: 0.25;
  z-index: 1;
  transition: opacity 200ms ease;
}

.lm_header .lm_tab {
  padding-top: 0px;
  margin-top: 0px;
}
</style>
