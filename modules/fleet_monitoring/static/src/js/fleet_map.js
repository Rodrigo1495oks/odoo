/** @odoo-module **/

import { registry } from "@web/core/registry";
const rpc = require('web.rpc');

const { Component, onMounted} = owl;
export class FleetMapComponent extends Component {
    setup() {
        const map = owl.useRef("map_div");

        onMounted(async () => {
            let data = await rpc.query({model: 'res.company',method: 'get_lat_long',args: [[]]});
            var L = window.L;
            var w_map = L.map(map.el).setView(data, 5);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '&amp;copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(w_map);
            this.map = w_map;
            this.marker_list = [];
            this.get_map_data()
            this.get_data_with_interval()
          });
    }

    get_map_data() {
        var self = this;
        var rpccall =  rpc.query({
            model: 'fleet.vehicle',
            method: 'get_map_data',
            args:[[]],
            }).then(function(result) {
                self.delete_old_marker();
                self.render_map_data(result);
            });
    }

    get_data_with_interval() {
        var time = 10 //Seconds
        time = time*1000
        var self = this;
        var interval = window.setInterval(function(){
           self.get_map_data(); 
        }, time);
    }

    render_map_data(data) {
        var img = L.icon({iconUrl: "/fleet_monitoring/static/description/icon.png",iconSize:[40, 40]});
        var i;
        for (i = 0; i < data.length; i++) {
            var driver = data[i].driver_id && data[i].driver_id[1]
            var popup = '<p>Name: </p><span>'+data[i].display_name+'</span><br/><p>Driver Name: </p><span>'+ driver +'</span>'
            var m = L.marker([data[i].latitude,data[i].longitude],{icon:img}).addTo(this.map).bindPopup(popup)
            this.map.addLayer(m);
            this.marker_list.push(m);                
        }
    }

    delete_old_marker() {for (var i = 0; i < this.marker_list.length; i++) {this.map.removeLayer(this.marker_list[i])}}

}

FleetMapComponent.template = "fleet_monitoring.FleetMap";
registry.category("actions").add("action_fleet_monitoring", FleetMapComponent);
